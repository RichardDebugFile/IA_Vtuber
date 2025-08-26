# services/voice/src/tools/try_say.py
import argparse
import os
import tempfile
import requests

# Para reproducir en Windows sin dependencias extra
try:
    import winsound
except Exception:
    winsound = None


def healthcheck(base_url: str) -> None:
    url = base_url.rstrip("/") + "/health"
    r = requests.get(url, timeout=5)
    try:
        r.raise_for_status()
    except Exception:
        print(f"[x] Healthcheck FALLÓ {url}")
        print(r.text)
        raise
    print(f"[✓] Healthcheck OK {url} ->", r.json())


def synthesize(
    base_url: str,
    text: str,
    emotion: str | None,
    style: str | None,
    speaker_id: str | None,
    rvc_enabled: bool,
    rvc_key: int,
    rvc_f0_method: str,
    rvc_index_rate: float,
    rvc_volume: float,
    sample_rate: int | None,
    out_path: str | None,
    play: bool,
):
    url = base_url.rstrip("/") + "/speak"

    body = {
        "text": text,
        "emotion": emotion,
        "style": style,
        "speaker_id": speaker_id,
        "sample_rate": sample_rate,
        "rvc": {
            "enabled": rvc_enabled,
            "key": rvc_key,
            "f0_method": rvc_f0_method,
            "index_rate": rvc_index_rate,
            "volume": rvc_volume,
        },
    }

    # Si queremos archivo/escuchar => mejor pedir WAV directamente
    want_wav = bool(out_path or play)
    headers = {"Accept": "audio/wav" if want_wav else "application/json"}

    r = requests.post(url, json=body, headers=headers, timeout=300)
    r.raise_for_status()

    if want_wav:
        # Guardar WAV
        if not out_path:
            fd, tmp = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            out_path = tmp
        with open(out_path, "wb") as f:
            f.write(r.content)
        print(f"[✓] WAV guardado en: {out_path}")

        if play:
            if winsound:
                print("[i] Reproduciendo…")
                winsound.PlaySound(out_path, winsound.SND_FILENAME)
            else:
                print("[i] Instala 'simpleaudio' o usa un reproductor externo.")
        return

    # Si pedimos JSON
    print(r.json())


def main():
    ap = argparse.ArgumentParser(description="Probar el microservicio de VOZ (/speak).")
    ap.add_argument("--base", default="http://127.0.0.1:8810", help="URL del voice service")
    ap.add_argument("--text", required=True, help="Texto a sintetizar")
    ap.add_argument("--emotion", default=None, help="Emoción (happy, sad, angry, etc.)")
    ap.add_argument("--style", default=None, help="Estilo opcional")
    ap.add_argument("--speaker-id", default=None, help="ID de locutor (si lo usas)")
    ap.add_argument("--sample-rate", type=int, default=None, help="SR deseado (p.ej., 24000)")

    # Opciones RVC
    ap.add_argument("--rvc-enabled", action="store_true", help="Activar Voice Conversion")
    ap.add_argument("--rvc-key", type=int, default=0)
    ap.add_argument("--rvc-f0-method", default="pm", choices=["pm", "harvest", "dio", "rmvpe"])
    ap.add_argument("--rvc-index-rate", type=float, default=0.5)
    ap.add_argument("--rvc-volume", type=float, default=1.0)

    ap.add_argument("--out", default=None, help="Ruta para guardar el WAV")
    ap.add_argument("--play", action="store_true", help="Reproducir al terminar (Windows: winsound)")

    args = ap.parse_args()

    healthcheck(args.base)

    synthesize(
        base_url=args.base,
        text=args.text,
        emotion=args.emotion,
        style=args.style,
        speaker_id=args.speaker_id,
        rvc_enabled=args.rvc_enabled,
        rvc_key=args.rvc_key,
        rvc_f0_method=args.rvc_f0_method,
        rvc_index_rate=args.rvc_index_rate,
        rvc_volume=args.rvc_volume,
        sample_rate=args.sample_rate,
        out_path=args.out,
        play=args.play,
    )


if __name__ == "__main__":
    main()
