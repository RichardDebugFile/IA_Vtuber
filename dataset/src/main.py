"""Dataset Generator FastAPI Application."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .generator import DatasetGenerator
from .state_manager import StateManager
from .websocket_manager import ConnectionManager
from .models import GenerationConfig
from .content_generator import ContentGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Dataset Generator",
    description="Generate audio dataset for VTuber voice training",
    version="1.0.0"
)

# Initialize managers
state_manager = StateManager(Path("generation_state.json"))
ws_manager = ConnectionManager()
generator = DatasetGenerator(
    state_manager=state_manager,
    ws_manager=ws_manager,
    wavs_dir=Path("wavs")
)

# Mount static files
STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Pydantic models for requests
class StartRequest(BaseModel):
    """Request model for starting generation."""
    parallel_workers: int = 4
    backend: str = "http"


class RegenerateRequest(BaseModel):
    """Request model for regenerating an entry."""
    entry_id: int
    emotion: Optional[str] = None  # Optional emotion override


class ResetFromRequest(BaseModel):
    """Request model for resetting from a specific ID."""
    start_from_id: int


# Routes

@app.get("/")
async def root():
    """Serve the main web interface."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Web interface not found")
    return FileResponse(index_file)


@app.get("/api/status")
async def get_status():
    """Get current generation status and statistics."""
    try:
        summary = state_manager.get_summary()
        return {"ok": True, "status": summary}
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/api/entries")
async def get_entries(
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None
):
    """
    Get list of audio entries.

    Args:
        limit: Maximum number of entries to return
        offset: Number of entries to skip
        status_filter: Filter by status (pending, generating, completed, error)
    """
    try:
        state = state_manager.load_state()
        entries = state.entries

        # Apply filter
        if status_filter:
            entries = [e for e in entries if e.status == status_filter]

        # Apply pagination
        total = len(entries)
        paginated = entries[offset:offset + limit]

        return {
            "ok": True,
            "entries": [e.model_dump(mode='json') for e in paginated],
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Error getting entries: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/start")
async def start_generation(request: StartRequest):
    """Start the generation process."""
    try:
        # Check if already running
        state = state_manager.load_state()
        if state.status == "running":
            return {"ok": False, "error": "Generation already running"}

        # Create config
        config = GenerationConfig(
            total_clips=state.total_clips,
            parallel_workers=request.parallel_workers,
            backend=request.backend
        )

        # Start generation in background
        import asyncio
        asyncio.create_task(generator.start_generation(config))

        return {"ok": True, "message": "Generation started"}

    except Exception as e:
        logger.error(f"Error starting generation: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/pause")
async def pause_generation():
    """Pause the generation process."""
    try:
        await generator.pause()
        return {"ok": True, "message": "Generation paused"}
    except Exception as e:
        logger.error(f"Error pausing generation: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/resume")
async def resume_generation():
    """Resume the paused generation process."""
    try:
        await generator.resume()
        return {"ok": True, "message": "Generation resumed"}
    except Exception as e:
        logger.error(f"Error resuming generation: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/stop")
async def stop_generation():
    """Stop the generation process."""
    try:
        await generator.stop()
        return {"ok": True, "message": "Generation stopped"}
    except Exception as e:
        logger.error(f"Error stopping generation: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/force_priority_check")
async def force_priority_check():
    """Force an immediate priority check on the next loop iteration."""
    try:
        success = await generator.force_check_priorities()
        if success:
            return {"ok": True, "message": "Priority check will be forced on next iteration"}
        else:
            return {"ok": False, "error": "Generation is not running"}
    except Exception as e:
        logger.error(f"Error forcing priority check: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/regenerate")
async def regenerate_entry(request: RegenerateRequest):
    """Regenerate a failed audio entry."""
    try:
        await generator.regenerate_entry(request.entry_id, emotion=request.emotion)
        emotion_msg = f" with emotion '{request.emotion}'" if request.emotion else ""
        return {"ok": True, "message": f"Regenerating entry {request.entry_id}{emotion_msg}"}
    except Exception as e:
        logger.error(f"Error regenerating entry: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    """
    Stream an audio file.

    Args:
        filename: Name of the audio file (e.g., casiopy_0001.wav)
    """
    try:
        file_path = Path("wavs") / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found")

        return FileResponse(
            file_path,
            media_type="audio/wav",
            filename=filename
        )

    except Exception as e:
        logger.error(f"Error serving audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/services")
async def check_services():
    """Check status of TTS and Fish Speech services."""
    try:
        service_status = await generator.check_services()
        return {"ok": True, "services": service_status}
    except Exception as e:
        logger.error(f"Error checking services: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/sync_state")
async def sync_state():
    """
    Synchronize state with actual audio files on disk.
    Updates entry statuses based on file existence.

    This fixes race condition issues where:
    - Files exist but are marked as pending
    - Files don't exist but are marked as completed
    """
    try:
        # Stop any running generation first
        if generator.is_running:
            await generator.stop()
            logger.info("Stopped generation before sync")

        wavs_dir = Path("wavs")
        result = state_manager.sync_with_files(wavs_dir)

        # Force status to idle and save (sync doesn't change status)
        state = state_manager.load_state()
        state.status = "idle"
        state_manager.save_state(state)

        # Broadcast updated status and reload entries
        await ws_manager.broadcast_status("idle")

        # Broadcast entry updates for all synced entries
        if result['synced_entries'] > 0:
            state = state_manager.load_state()
            for entry in state.entries:
                await ws_manager.broadcast_entry_update(entry.model_dump(mode='json'))

        logger.info(
            f"State synchronized: {result['files_found']} found, {result['files_missing']} missing, "
            f"{result['synced_entries']} entries updated, {result['completed_after']} now completed"
        )

        return {
            "ok": True,
            "message": f"Estado sincronizado: {result['synced_entries']} audios actualizados",
            "synced_entries": result['synced_entries'],
            "completed_before": result['completed_before'],
            "completed_after": result['completed_after'],
            "total_entries": result['total_entries'],
            "files_found": result['files_found'],
            "files_missing": result['files_missing']
        }

    except Exception as e:
        logger.error(f"Error syncing state: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/reset_from")
async def reset_from_id(request: ResetFromRequest):
    """
    Reset generation from a specific entry ID.
    Marks all entries from start_from_id onwards as pending.
    """
    try:
        state = state_manager.load_state()

        if request.start_from_id < 1 or request.start_from_id > state.total_clips:
            return {
                "ok": False,
                "error": f"ID debe estar entre 1 y {state.total_clips}"
            }

        # Count how many will be reset
        reset_count = 0

        # Reset entries from start_from_id onwards
        for entry in state.entries:
            if entry.id >= request.start_from_id:
                # Update counters based on current status
                if entry.status == "completed":
                    state.completed -= 1
                    # Delete audio file if exists
                    audio_file = Path("wavs") / f"{entry.filename}.wav"
                    if audio_file.exists():
                        audio_file.unlink()
                elif entry.status == "error":
                    state.failed -= 1

                # Reset entry
                entry.status = "pending"
                entry.error_message = None
                entry.duration_seconds = None
                entry.file_size_kb = None
                entry.generated_at = None

                reset_count += 1

        # Save updated state
        state_manager.save_state(state)

        # Broadcast status update
        await ws_manager.broadcast_status(state.status)

        logger.info(
            f"Reset {reset_count} entries from ID {request.start_from_id}. "
            f"New stats: {state.completed} completed, {state.failed} failed"
        )

        return {
            "ok": True,
            "message": f"Reset {reset_count} entries from ID {request.start_from_id}",
            "reset_count": reset_count,
            "new_completed": state.completed,
            "new_failed": state.failed
        }

    except Exception as e:
        logger.error(f"Error resetting from ID: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/initialize")
async def initialize_dataset():
    """Initialize dataset by generating metadata and state."""
    try:
        # Check if metadata.csv exists
        metadata_file = Path("metadata.csv")

        if metadata_file.exists() and metadata_file.stat().st_size > 0:
            # Load from existing CSV
            logger.info("Loading from existing metadata.csv")
            state = state_manager.initialize_from_csv(metadata_file)
        else:
            # Generate new dataset content
            logger.info("Generating new dataset content")
            dataset = ContentGenerator.generate_dataset(2000)

            # Save to pipe-separated format (filename|text)
            with open(metadata_file, 'w', encoding='utf-8') as f:
                for entry in dataset:
                    f.write(f"{entry['filename']}|{entry['text']}\n")

            # Initialize state
            state = state_manager.initialize_from_csv(metadata_file)

            # Get text statistics
            stats = ContentGenerator.get_text_stats(dataset)
            logger.info(f"Generated dataset: {stats['total_entries']} entries, {stats['unique_texts']} unique texts")

        return {
            "ok": True,
            "message": f"Dataset initialized with {state.total_clips} entries",
            "total_clips": state.total_clips
        }

    except Exception as e:
        logger.error(f"Error initializing dataset: {e}")
        return {"ok": False, "error": str(e)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await ws_manager.connect(websocket)

    try:
        # Send initial status
        summary = state_manager.get_summary()
        await ws_manager.send_personal_message(
            {"type": "status", "data": summary},
            websocket
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any client messages if needed
                logger.debug(f"Received WebSocket message: {data}")

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(f"WebSocket error: {e}")

    finally:
        ws_manager.disconnect(websocket)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Shutting down dataset generator...")
    await generator.cleanup()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8801)
