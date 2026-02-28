"""State persistence manager for dataset generation."""

import json
from pathlib import Path
from typing import Optional
import logging
from .models import GenerationState, GenerationConfig, AudioEntry

logger = logging.getLogger(__name__)


class StateManager:
    """Manage generation state persistence to JSON file."""

    def __init__(self, state_file: Path = Path("generation_state.json")):
        """
        Initialize state manager.

        Args:
            state_file: Path to state JSON file
        """
        self.state_file = state_file
        self._lock = None  # For thread safety if needed

    def load_state(self) -> GenerationState:
        """
        Load generation state from file.

        Returns:
            GenerationState object (creates new if file doesn't exist)
        """
        if not self.state_file.exists():
            logger.info("No existing state file, creating new state")
            return self._create_initial_state()

        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Convert datetime strings back to datetime objects
            for entry in data.get("entries", []):
                if entry.get("generated_at"):
                    # Keep as string for now, Pydantic will handle conversion
                    pass

            state = GenerationState(**data)
            logger.info(
                f"Loaded state: {state.completed}/{state.total_clips} completed, "
                f"status={state.status}"
            )
            return state

        except Exception as e:
            logger.error(f"Error loading state: {e}")
            logger.info("Creating new state due to load error")
            return self._create_initial_state()

    def save_state(self, state: GenerationState) -> bool:
        """
        Save generation state to file.

        Args:
            state: GenerationState to save

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert to dict for JSON serialization
            state_dict = state.model_dump(mode='json')

            # Save to file with pretty printing
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_dict, f, indent=2, ensure_ascii=False)

            logger.debug(f"State saved: {state.completed}/{state.total_clips} completed")
            return True

        except Exception as e:
            logger.error(f"Error saving state: {e}")
            return False

    def _create_initial_state(self) -> GenerationState:
        """Create a new initial state."""
        config = GenerationConfig()
        return GenerationState(
            status="idle",
            current_index=0,
            total_clips=0,
            completed=0,
            failed=0,
            config=config,
            entries=[]
        )

    def initialize_from_csv(self, csv_file: Path) -> GenerationState:
        """
        Initialize state from metadata file (pipe-separated format).

        Args:
            csv_file: Path to metadata.csv (format: filename|text)

        Returns:
            GenerationState with entries populated from file
        """
        entries = []

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                for idx, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue

                    # Parse pipe-separated format: filename|text
                    parts = line.split('|', 1)
                    if len(parts) != 2:
                        logger.warning(f"Skipping invalid line {idx}: {line[:50]}")
                        continue

                    filename, text = parts

                    entry = AudioEntry(
                        id=idx,
                        filename=filename,
                        text=text,
                        status="pending"
                    )
                    entries.append(entry)

            logger.info(f"Initialized {len(entries)} entries from pipe-separated file")

            config = GenerationConfig(total_clips=len(entries))
            state = GenerationState(
                status="idle",
                total_clips=len(entries),
                config=config,
                entries=entries
            )

            # Save initial state
            self.save_state(state)

            return state

        except Exception as e:
            logger.error(f"Error initializing from CSV: {e}")
            raise

    def reset_state(self) -> bool:
        """
        Reset state by deleting the state file.

        Returns:
            True if successful
        """
        try:
            if self.state_file.exists():
                self.state_file.unlink()
                logger.info("State file deleted")
            return True
        except Exception as e:
            logger.error(f"Error resetting state: {e}")
            return False

    def sync_with_files(self, wavs_dir: Path) -> dict:
        """
        Synchronize state with actual audio files on disk.
        Updates entry status based on file existence.

        Args:
            wavs_dir: Directory containing WAV files

        Returns:
            Dictionary with sync results
        """
        import soundfile as sf
        from datetime import datetime

        state = self.load_state()
        synced_count = 0
        completed_before = state.completed
        failed_before = state.failed
        files_found = 0
        files_missing = 0

        logger.info(f"Syncing state with files in {wavs_dir}")

        for entry in state.entries:
            audio_file = wavs_dir / f"{entry.filename}.wav"

            # If file exists but entry is pending/error, update it
            if audio_file.exists():
                files_found += 1
                if entry.status in ["pending", "error"]:
                    try:
                        # Update counters based on CURRENT status (before changing it)
                        was_error = entry.status == "error"

                        # Read audio file to get metadata
                        audio_data, sample_rate = sf.read(audio_file)
                        duration = len(audio_data) / sample_rate
                        file_size = audio_file.stat().st_size

                        # Update entry
                        entry.status = "completed"
                        entry.duration_seconds = duration
                        entry.file_size_kb = file_size // 1024
                        entry.generated_at = datetime.fromtimestamp(audio_file.stat().st_mtime)
                        entry.error_message = None

                        # Update counters
                        if was_error:
                            state.failed -= 1
                        state.completed += 1

                        synced_count += 1
                        logger.info(f"Synced {entry.filename}: file exists, marked as completed")

                    except Exception as e:
                        logger.error(f"Error reading {entry.filename}: {e}")

            # If file doesn't exist but entry is not pending, mark as pending
            elif not audio_file.exists():
                files_missing += 1
                if entry.status != "pending":
                    # Update counters based on current status
                    if entry.status == "completed":
                        state.completed -= 1
                    elif entry.status == "error":
                        state.failed -= 1

                    # Reset entry to pending
                    entry.status = "pending"
                    entry.duration_seconds = None
                    entry.file_size_kb = None
                    entry.generated_at = None
                    entry.error_message = None

                    synced_count += 1
                    logger.info(f"Synced {entry.filename}: file missing, marked as pending")

        # Save updated state
        self.save_state(state)

        logger.info(
            f"Sync complete: {files_found} files found, {files_missing} missing, "
            f"{synced_count} entries updated"
        )

        return {
            "synced_entries": synced_count,
            "completed_before": completed_before,
            "completed_after": state.completed,
            "failed_before": failed_before,
            "failed_after": state.failed,
            "total_entries": state.total_clips,
            "files_found": files_found,
            "files_missing": files_missing
        }

    def get_summary(self) -> dict:
        """
        Get summary statistics from current state.

        Returns:
            Dictionary with summary statistics
        """
        state = self.load_state()

        pending = sum(1 for e in state.entries if e.status == "pending")
        generating = sum(1 for e in state.entries if e.status == "generating")
        completed = sum(1 for e in state.entries if e.status == "completed")
        failed = sum(1 for e in state.entries if e.status == "error")

        total_duration = sum(
            e.duration_seconds or 0
            for e in state.entries
            if e.duration_seconds
        )

        total_size = sum(
            e.file_size_kb or 0
            for e in state.entries
            if e.file_size_kb
        )

        return {
            "status": state.status,
            "total_clips": state.total_clips,
            "pending": pending,
            "generating": generating,
            "completed": completed,
            "failed": failed,
            "total_duration_seconds": round(total_duration, 2),
            "total_duration_formatted": f"{int(total_duration // 3600)}h {int((total_duration % 3600) // 60)}m {int(total_duration % 60)}s",
            "total_size_mb": round(total_size / 1024, 2),
            "progress_percentage": round((completed / state.total_clips * 100) if state.total_clips > 0 else 0, 1)
        }
