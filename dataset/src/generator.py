"""Dataset generation engine with async processing."""

import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

from .models import AudioEntry, GenerationState, GenerationConfig
from .tts_client import TTSClient
from .audio_processor import AudioProcessor
from .state_manager import StateManager
from .websocket_manager import ConnectionManager

logger = logging.getLogger(__name__)


class DatasetGenerator:
    """Main dataset generation engine."""

    def __init__(
        self,
        state_manager: StateManager,
        ws_manager: ConnectionManager,
        wavs_dir: Path = Path("wavs")
    ):
        """
        Initialize dataset generator.

        Args:
            state_manager: State persistence manager
            ws_manager: WebSocket connection manager
            wavs_dir: Directory to save generated audio files
        """
        self.state_manager = state_manager
        self.ws_manager = ws_manager
        self.wavs_dir = wavs_dir
        self.tts_client = TTSClient()

        self.is_running = False
        self.is_paused = False
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.generation_task: Optional[asyncio.Task] = None
        self.force_priority_check = False  # Flag to force immediate priority check
        self.pending_individual_regenerations = set()  # Queue for individual regenerations

        # Ensure wavs directory exists
        self.wavs_dir.mkdir(parents=True, exist_ok=True)

    async def start_generation(self, config: Optional[GenerationConfig] = None):
        """
        Start dataset generation process.

        Args:
            config: Generation configuration (uses existing if None)
        """
        if self.is_running:
            logger.warning("Generation already running")
            return

        self.is_running = True
        self.is_paused = False

        # Load state
        state = self.state_manager.load_state()

        # Reset stuck 'generating' entries to 'pending' (from previous crashed sessions)
        stuck_count = 0
        for entry in state.entries:
            if entry.status == "generating":
                entry.status = "pending"
                entry.error_message = None
                stuck_count += 1

        if stuck_count > 0:
            logger.info(f"Reset {stuck_count} stuck 'generating' entries to 'pending'")

        # Update config if provided
        if config:
            state.config = config

        # Update status
        state.status = "running"
        self.state_manager.save_state(state)
        await self.ws_manager.broadcast_status("running")

        # Create semaphore for parallel workers
        self.semaphore = asyncio.Semaphore(state.config.parallel_workers)

        logger.info(
            f"Starting generation: {state.total_clips} clips with "
            f"{state.config.parallel_workers} parallel workers"
        )

        # Broadcast log: starting generation
        pending_count = sum(1 for e in state.entries if e.status == "pending")
        await self.ws_manager.broadcast_log(
            f"🚀 Iniciando generación: {pending_count} audios pendientes con {state.config.parallel_workers} workers paralelos",
            level="info"
        )

        # Process in batches of 50 with priority checks
        await self._process_generation_with_priority_checks(state)

        # After processing pending, handle retries for failed entries
        if self.is_running and not self.is_paused:
            await self._process_retries()

        # Mark as completed or stopped based on final state
        state = self.state_manager.load_state()

        if self.is_running and not self.is_paused:
            # Generation completed normally
            state.status = "completed"
            self.state_manager.save_state(state)
            await self.ws_manager.broadcast_status("completed")

            logger.info(
                f"Generation completed: {state.completed} successful, "
                f"{state.failed} failed"
            )

            # Broadcast log: generation completed
            await self.ws_manager.broadcast_log(
                f"🎉 Generación completada: {state.completed} exitosos, {state.failed} fallidos de {state.total_clips} total",
                level="success"
            )
        else:
            # Generation was stopped or paused
            final_status = "stopped" if not self.is_paused else "paused"
            state.status = final_status
            self.state_manager.save_state(state)
            await self.ws_manager.broadcast_status(final_status)

            logger.info(
                f"Generation {final_status}: {state.completed} successful, "
                f"{state.failed} failed"
            )

            # Broadcast log: generation stopped
            await self.ws_manager.broadcast_log(
                f"⏸️ Generación {final_status}: {state.completed} exitosos, {state.failed} fallidos procesados hasta el momento",
                level="warning"
            )

        self.is_running = False

    async def _process_generation_with_priority_checks(self, state: GenerationState):
        """
        Process generation in mixed batches with balanced priority handling.

        Strategy:
        - Each batch processes up to 10 audios total
        - Priorities (custom emotions) get up to 5 slots per batch
        - Regular pending entries fill remaining slots
        - This ensures regular entries are NEVER blocked by priorities
        """
        BATCH_SIZE = 10  # Total audios per batch
        MAX_PRIORITIES_PER_BATCH = 5  # Max priority slots (rest for regular)
        PROGRESS_LOG_INTERVAL = 50  # Log progress every 50 audios
        processed_count = 0

        while self.is_running and not self.is_paused:
            # Reload state to get current status
            state = self.state_manager.load_state()

            # Reset force flag if set
            if self.force_priority_check:
                self.force_priority_check = False
                logger.info("Forced priority check triggered by user")
                await self.ws_manager.broadcast_log(
                    f"⚡ Verificación forzada de prioridades activada por el usuario",
                    level="warning"
                )

            # Get priority entries (custom emotions)
            priority_entries = [
                e for e in state.entries
                if e.status == "pending" and e.emotion is not None
            ]

            # Get regular pending entries (no custom emotion)
            regular_pending = [
                e for e in state.entries
                if e.status == "pending" and e.emotion is None
            ]

            # Check if we have any work to do
            if not priority_entries and not regular_pending:
                # No more pending entries of any kind
                break

            # Build mixed batch: priorities first (limited), then regular
            current_batch = []

            # Add priorities (max 5 per batch to not block regular)
            if priority_entries:
                priority_batch = priority_entries[:MAX_PRIORITIES_PER_BATCH]
                current_batch.extend(priority_batch)

                logger.info(
                    f"Adding {len(priority_batch)} priority entries to batch "
                    f"({len(priority_entries)} total priorities pending)"
                )

            # Fill remaining slots with regular entries
            remaining_slots = BATCH_SIZE - len(current_batch)
            if remaining_slots > 0 and regular_pending:
                regular_batch = regular_pending[:remaining_slots]
                current_batch.extend(regular_batch)

            # Check if we have anything to process
            if not current_batch:
                break

            # Log batch composition
            priority_count = sum(1 for e in current_batch if e.emotion is not None)
            regular_count = len(current_batch) - priority_count

            logger.info(
                f"Processing mixed batch: {priority_count} priorities + "
                f"{regular_count} regular = {len(current_batch)} total "
                f"(processed so far: {processed_count})"
            )

            if priority_count > 0:
                await self.ws_manager.broadcast_log(
                    f"⭐ Batch mixto: {priority_count} prioritarios + {regular_count} regulares",
                    level="info"
                )

            # Process entire batch in parallel
            tasks = []
            for entry in current_batch:
                if not self.is_running or self.is_paused:
                    break
                task = asyncio.create_task(self._generate_audio(entry))
                tasks.append(task)

                # Remove from individual regeneration queue if present
                self.pending_individual_regenerations.discard(entry.id)

            if tasks:
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    logger.error(f"Error processing mixed batch: {e}")

            processed_count += len(current_batch)

            # Every 50 entries, log progress
            if processed_count % PROGRESS_LOG_INTERVAL == 0:
                state = self.state_manager.load_state()
                await self.ws_manager.broadcast_log(
                    f"📊 Progreso: {state.completed} completados, {state.failed} fallidos",
                    level="info"
                )

    async def _generate_audio(self, entry: AudioEntry):
        """
        Generate a single audio file.
        This method is exception-safe and will never crash the generation process.

        Args:
            entry: AudioEntry to generate
        """
        try:
            async with self.semaphore:
                # Check if stopped or paused
                while self.is_paused and self.is_running:
                    await asyncio.sleep(0.5)

                if not self.is_running:
                    return

                # Update status to generating
                entry.status = "generating"
                await self._update_entry(entry)

                # Load state once at the beginning
                state = self.state_manager.load_state()

                # Find the actual entry in state (not the passed reference)
                state_entry = next((e for e in state.entries if e.id == entry.id), None)
                if not state_entry:
                    logger.error(f"Entry {entry.id} not found in state")
                    return

                try:
                    logger.info(f"Generating {entry.filename}: '{entry.text[:50]}...'")

                    # Broadcast log: starting generation
                    emotion_text = f" con emoción '{state_entry.emotion}'" if state_entry.emotion else ""
                    await self.ws_manager.broadcast_log(
                        f"🎙️ Generando {entry.filename}: {entry.text[:60]}...{emotion_text}",
                        level="generating"
                    )

                    # Synthesize audio (use entry.emotion if set, otherwise auto-detect)
                    audio_bytes = await self.tts_client.synthesize(
                        text=entry.text,
                        backend=state.config.backend,
                        emotion=state_entry.emotion  # Use stored emotion or None for auto-detect
                    )

                    if not audio_bytes:
                        raise Exception("TTS synthesis returned no data")

                    # Process and save audio (add .wav extension)
                    output_path = self.wavs_dir / f"{entry.filename}.wav"
                    metadata = await AudioProcessor.process_and_save(
                        audio_bytes,
                        output_path,
                        target_db=-3.0
                    )

                    # Update entry in state with success
                    state_entry.status = "completed"
                    state_entry.duration_seconds = metadata["duration_seconds"]
                    state_entry.file_size_kb = metadata["file_size_kb"]
                    state_entry.generated_at = datetime.now()

                    # Update state counters
                    state.completed += 1

                    logger.info(
                        f"✓ {entry.filename} completed "
                        f"({state.completed}/{state.total_clips})"
                    )

                    # Broadcast log: success
                    await self.ws_manager.broadcast_log(
                        f"✅ {entry.filename} completado ({metadata['duration_seconds']:.1f}s, {metadata['file_size_kb']}KB) - Progreso: {state.completed}/{state.total_clips}",
                        level="success"
                    )

                except Exception as e:
                    # Update entry in state with error
                    state_entry.status = "error"
                    state_entry.error_message = str(e)

                    # Update state counters
                    state.failed += 1

                    logger.error(f"✗ {entry.filename} failed: {e}")

                    # Broadcast log: error
                    await self.ws_manager.broadcast_log(
                        f"❌ {entry.filename} falló: {str(e)[:100]}",
                        level="error"
                    )

                # CRITICAL: Reload state before saving to prevent race conditions
                # This ensures we don't overwrite changes made by other parallel workers
                fresh_state = self.state_manager.load_state()

                # Find and update the entry in the fresh state
                fresh_entry = next((e for e in fresh_state.entries if e.id == entry.id), None)
                if fresh_entry:
                    # Copy all updated fields from our local state_entry
                    fresh_entry.status = state_entry.status
                    fresh_entry.duration_seconds = state_entry.duration_seconds
                    fresh_entry.file_size_kb = state_entry.file_size_kb
                    fresh_entry.generated_at = state_entry.generated_at
                    fresh_entry.error_message = state_entry.error_message

                    # Update counters in fresh state
                    if state_entry.status == "completed":
                        fresh_state.completed += 1
                    elif state_entry.status == "error":
                        fresh_state.failed += 1

                    # Save the fresh state (not our old copy)
                    self.state_manager.save_state(fresh_state)

                    # Broadcast updates
                    await self._update_entry(fresh_entry)
                    await self._broadcast_progress()
                else:
                    logger.error(f"Entry {entry.id} not found in fresh state!")
                    # Fallback: save our state anyway
                    self.state_manager.save_state(state)
                    await self._update_entry(state_entry)
                    await self._broadcast_progress()

                # Small delay to prevent overwhelming Docker with long phrases
                await asyncio.sleep(0.5)

        except Exception as critical_error:
            # Catch any unhandled exception to prevent process crash
            logger.critical(
                f"CRITICAL ERROR in _generate_audio for {entry.filename}: {critical_error}",
                exc_info=True
            )
            # Mark as error to prevent infinite loops
            try:
                state = self.state_manager.load_state()
                state_entry = next((e for e in state.entries if e.id == entry.id), None)
                if state_entry:
                    state_entry.status = "error"
                    state_entry.error_message = f"Critical error: {str(critical_error)}"
                    state.failed += 1
                    self.state_manager.save_state(state)
            except Exception as save_error:
                logger.error(f"Could not save error state: {save_error}")

    async def _process_retries(self):
        """
        Process automatic retries for failed entries.
        Runs after all pending entries are processed, without blocking.
        """
        state = self.state_manager.load_state()
        max_retries = state.config.max_retries

        # Find failed entries that can be retried
        retry_entries = [
            entry for entry in state.entries
            if entry.status == "error" and entry.retry_count < max_retries
        ]

        if not retry_entries:
            logger.info("No entries to retry")
            return

        logger.info(
            f"Starting automatic retries: {len(retry_entries)} entries "
            f"(max {max_retries} attempts per entry)"
        )

        # Process retries one by one (respecting semaphore)
        for entry in retry_entries:
            if not self.is_running or self.is_paused:
                break

            # Increment retry count
            entry.retry_count += 1

            # Reset to pending for retry
            entry.status = "pending"
            entry.error_message = None

            # Save state before retry
            self.state_manager.save_state(state)
            await self._update_entry(entry)

            logger.info(
                f"Retrying {entry.filename} "
                f"(attempt {entry.retry_count}/{max_retries})"
            )

            # Generate audio
            await self._generate_audio(entry)

            # If still failed after retry, update state
            if entry.status == "error":
                logger.warning(
                    f"{entry.filename} failed again "
                    f"({entry.retry_count}/{max_retries} attempts)"
                )

                # If max retries reached, log final failure
                if entry.retry_count >= max_retries:
                    logger.error(
                        f"{entry.filename} permanently failed after "
                        f"{max_retries} attempts: {entry.error_message}"
                    )

        # Final summary
        state = self.state_manager.load_state()
        still_failed = sum(1 for e in state.entries if e.status == "error")
        logger.info(
            f"Retry process completed. Remaining failures: {still_failed}"
        )

    async def pause(self):
        """Pause the generation process."""
        if not self.is_running:
            logger.warning("Cannot pause: generation not running")
            return

        self.is_paused = True

        state = self.state_manager.load_state()
        state.status = "paused"
        self.state_manager.save_state(state)

        await self.ws_manager.broadcast_status("paused")
        logger.info("Generation paused")

    async def resume(self):
        """Resume the paused generation process."""
        if not self.is_paused:
            logger.warning("Cannot resume: generation not paused")
            return

        self.is_paused = False

        state = self.state_manager.load_state()
        state.status = "running"
        self.state_manager.save_state(state)

        await self.ws_manager.broadcast_status("running")
        logger.info("Generation resumed")

    async def stop(self):
        """Stop the generation process."""
        if not self.is_running:
            logger.warning("Cannot stop: generation not running")
            return

        self.is_running = False
        self.is_paused = False

        state = self.state_manager.load_state()
        state.status = "stopped"
        self.state_manager.save_state(state)

        await self.ws_manager.broadcast_status("stopped")
        logger.info("Generation stopped")

    async def force_check_priorities(self):
        """Force an immediate priority check on the next loop iteration."""
        if not self.is_running:
            logger.warning("Cannot force priority check: generation not running")
            return False

        self.force_priority_check = True
        logger.info("Priority check will be forced on next iteration")

        await self.ws_manager.broadcast_log(
            f"⚡ Verificación de prioridades forzada. Se procesarán en el próximo ciclo.",
            level="warning"
        )

        return True

    async def regenerate_entry(self, entry_id: int, emotion: Optional[str] = None):
        """
        Regenerate a specific entry (failed or completed).

        When multiple regenerations are requested, they are queued and processed together.

        Args:
            entry_id: ID of entry to regenerate
            emotion: Optional emotion override (auto-detected if None)
        """
        state = self.state_manager.load_state()

        # Find entry
        entry = next((e for e in state.entries if e.id == entry_id), None)

        if not entry:
            logger.error(f"Entry {entry_id} not found")
            raise Exception(f"Entry {entry_id} not found")

        emotion_msg = f" with emotion '{emotion}'" if emotion else ""
        logger.info(f"Regenerating entry {entry_id} (current status: {entry.status}){emotion_msg}")

        # Update counters based on current status
        if entry.status == "error":
            state.failed -= 1
        elif entry.status == "completed":
            state.completed -= 1
            # Delete old audio file if exists
            old_file = self.wavs_dir / f"{entry.filename}.wav"
            if old_file.exists():
                old_file.unlink()
                logger.info(f"Deleted old audio file: {entry.filename}.wav")

        # Reset entry status (manual regeneration resets retry counter)
        entry.status = "pending"
        entry.error_message = None
        entry.duration_seconds = None
        entry.file_size_kb = None
        entry.generated_at = None
        entry.retry_count = 0  # Reset retry count for manual regeneration
        entry.emotion = emotion  # Set emotion override (None = auto-detect)

        self.state_manager.save_state(state)

        # Broadcast the status change
        await self._update_entry(entry)

        # Add to individual regeneration queue
        self.pending_individual_regenerations.add(entry_id)

        # Generate if not currently running full generation
        if not self.is_running:
            # Process all queued individual regenerations
            await self._process_individual_regenerations()
        else:
            logger.info(f"Entry {entry_id} queued for regeneration in current batch")

    async def _process_individual_regenerations(self):
        """
        Process all queued individual regenerations.

        This processes ONLY the audios that were manually selected for regeneration,
        not all pending audios.
        """
        if not self.pending_individual_regenerations:
            return

        # Get list of IDs to process
        entry_ids = list(self.pending_individual_regenerations)
        self.pending_individual_regenerations.clear()

        logger.info(f"Processing {len(entry_ids)} individual regenerations: {entry_ids}")

        # Load state and get entries
        state = self.state_manager.load_state()
        entries_to_process = [
            e for e in state.entries
            if e.id in entry_ids and e.status == "pending"
        ]

        if not entries_to_process:
            logger.warning("No pending entries found in regeneration queue")
            return

        # Set running flag
        self.is_running = True
        self.semaphore = asyncio.Semaphore(len(entries_to_process))  # Process all in parallel

        # Broadcast start message
        await self.ws_manager.broadcast_log(
            f"🔄 Procesando {len(entries_to_process)} regeneraciones individuales seleccionadas",
            level="info"
        )

        # Process all entries in parallel
        tasks = []
        for entry in entries_to_process:
            task = asyncio.create_task(self._generate_audio(entry))
            tasks.append(task)

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"Completed processing {len(entries_to_process)} individual regenerations")

            # Broadcast completion message
            await self.ws_manager.broadcast_log(
                f"✅ {len(entries_to_process)} regeneraciones individuales completadas",
                level="success"
            )
        except Exception as e:
            logger.error(f"Error processing individual regenerations: {e}")
        finally:
            self.is_running = False

    async def _update_entry(self, entry: AudioEntry):
        """
        Broadcast entry update via WebSocket.

        Args:
            entry: AudioEntry that was updated
        """
        await self.ws_manager.broadcast_entry_update(entry.model_dump(mode='json'))

    async def _broadcast_progress(self):
        """Broadcast current progress to all WebSocket clients."""
        state = self.state_manager.load_state()
        await self.ws_manager.broadcast_progress(
            completed=state.completed,
            total=state.total_clips,
            failed=state.failed
        )

    async def check_services(self) -> dict:
        """
        Check availability of TTS and Fish services.

        Returns:
            Dictionary with service status
        """
        tts_available = await self.tts_client.check_health()

        # For now, we assume Fish is available if TTS is (TTS proxies to Fish)
        fish_available = tts_available

        await self.ws_manager.broadcast_service_status(tts_available, fish_available)

        return {
            "tts_available": tts_available,
            "fish_available": fish_available
        }

    async def cleanup(self):
        """Cleanup resources."""
        await self.tts_client.close()
