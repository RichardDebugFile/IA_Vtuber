"""CLI tool for testing STT service."""
import argparse
import sys
from pathlib import Path

import httpx


def transcribe_file(file_path: str, url: str = "http://127.0.0.1:8806"):
    """Transcribe an audio file using the STT service.

    Args:
        file_path: Path to audio file
        url: Base URL of STT service
    """
    file_path = Path(file_path)

    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return 1

    print(f"Transcribing: {file_path.name}")
    print(f"Service URL: {url}")
    print("-" * 60)

    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "audio/wav")}
            data = {
                "language": "es",
                "include_timestamps": "false",
                "identify_speaker": "false",
            }

            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{url}/transcribe",
                    files=files,
                    data=data,
                )

        if response.status_code == 200:
            result = response.json()
            print(f"\nTranscription:")
            print(f"  Text: {result['text']}")
            print(f"  Language: {result['language']}")
            print(f"  Duration: {result['duration']:.2f}s")

            if result.get("speaker_id"):
                print(f"  Speaker: {result['speaker_id']} (confidence: {result['speaker_confidence']:.2f})")

            if result.get("segments"):
                print(f"\nSegments ({len(result['segments'])}):")
                for i, seg in enumerate(result["segments"], 1):
                    print(f"  [{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text']}")

            return 0
        else:
            print(f"\nError: {response.status_code}")
            print(response.text)
            return 1

    except httpx.ConnectError:
        print(f"\nError: Could not connect to STT service at {url}")
        print("Make sure the service is running:")
        print(f"  python -m uvicorn src.server:app --host 127.0.0.1 --port 8806")
        return 1

    except Exception as e:
        print(f"\nError: {e}")
        return 1


def check_health(url: str = "http://127.0.0.1:8806"):
    """Check STT service health.

    Args:
        url: Base URL of STT service
    """
    print(f"Checking service health: {url}")
    print("-" * 60)

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{url}/health")

        if response.status_code == 200:
            data = response.json()
            print(f"\nService Status: OK")
            print(f"  Model: {data['model']}")
            print(f"  Device: {data['device']}")
            print(f"  Speaker ID: {'enabled' if data['speaker_id_enabled'] else 'disabled'}")
            return 0
        else:
            print(f"\nError: {response.status_code}")
            print(response.text)
            return 1

    except httpx.ConnectError:
        print(f"\nError: Service not running at {url}")
        return 1

    except Exception as e:
        print(f"\nError: {e}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="STT Service CLI Tool")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8806",
        help="STT service URL (default: http://127.0.0.1:8806)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Transcribe command
    transcribe_parser = subparsers.add_parser("transcribe", help="Transcribe audio file")
    transcribe_parser.add_argument("file", help="Path to audio file")

    # Health command
    subparsers.add_parser("health", help="Check service health")

    args = parser.parse_args()

    if args.command == "transcribe":
        return transcribe_file(args.file, args.url)
    elif args.command == "health":
        return check_health(args.url)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
