"""Fix and synchronize generation state with actual files."""

import json
from pathlib import Path
from datetime import datetime


def fix_state():
    """Synchronize state with actual wav files."""

    # Load current state
    with open('generation_state.json', 'r', encoding='utf-8') as f:
        state = json.load(f)

    print("=== Fixing State ===\n")

    # Get all wav files
    wavs_dir = Path('wavs')
    wav_files = {}
    if wavs_dir.exists():
        for wav_file in wavs_dir.glob('*.wav'):
            wav_files[wav_file.stem] = wav_file

    print(f"Found {len(wav_files)} .wav files on disk")
    print(f"State has {len(state['entries'])} entries\n")

    # Track changes
    fixed_count = 0
    marked_pending = 0

    # Process each entry
    for entry in state['entries']:
        filename = entry['filename']
        current_status = entry['status']
        wav_path = wav_files.get(filename)

        # If file exists but entry is not completed
        if wav_path and current_status != 'completed':
            try:
                # Get file metadata
                file_size = wav_path.stat().st_size

                # Estimate duration (very rough: ~6 seconds for 14 words avg)
                # This will be corrected when the file is properly processed
                estimated_duration = 6.0

                # Update entry
                entry['status'] = 'completed'
                entry['duration_seconds'] = estimated_duration
                entry['file_size_kb'] = file_size // 1024
                entry['generated_at'] = datetime.fromtimestamp(wav_path.stat().st_mtime).isoformat()
                entry['error_message'] = None

                fixed_count += 1
                print(f"[OK] Fixed {filename}: {current_status} -> completed")

            except Exception as e:
                print(f"[ERROR] Error reading {filename}: {e}")

        # If file doesn't exist but entry is completed
        elif not wav_path and current_status == 'completed':
            entry['status'] = 'pending'
            entry['duration_seconds'] = None
            entry['file_size_kb'] = None
            entry['generated_at'] = None
            entry['error_message'] = None
            entry['retry_count'] = 0

            marked_pending += 1
            print(f"[WARNING] Marked {filename} as pending (file missing)")

    # Recalculate counters
    real_completed = sum(1 for e in state['entries'] if e['status'] == 'completed')
    real_failed = sum(1 for e in state['entries'] if e['status'] == 'error')

    print(f"\n=== Summary ===")
    print(f"Fixed entries: {fixed_count}")
    print(f"Marked as pending: {marked_pending}")
    print(f"\nUpdating counters:")
    print(f"  Completed: {state['completed']} -> {real_completed}")
    print(f"  Failed: {state['failed']} -> {real_failed}")

    state['completed'] = real_completed
    state['failed'] = real_failed
    state['status'] = 'idle'  # Reset to idle

    # Save fixed state
    with open('generation_state.json', 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    print(f"\n[SUCCESS] State fixed and saved!")
    print(f"\nNext steps:")
    print(f"  1. Restart the server (start.bat)")
    print(f"  2. Click 'Iniciar' to continue from where it left off")
    print(f"  3. {2000 - real_completed} audios remaining")


if __name__ == '__main__':
    fix_state()
