import os, sys, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OA   = ROOT / "third_party" / "openaudio"   # repo de fish-speech
if not OA.exists():
    print("[fish] ERROR: falta third_party/openaudio (git clone https://github.com/fishaudio/fish-speech)")
    sys.exit(1)

# Carga .env de services/voice si existe
from dotenv import load_dotenv
load_dotenv(ROOT / "services" / "voice" / ".env")

listen = os.getenv("FISH_LISTEN", "127.0.0.1:9080")
ckpt   = os.getenv("FISH_CKPT", str(OA / "checkpoints" / "openaudio-s1-mini"))
codec  = os.getenv("FISH_DECODER", str(Path(ckpt) / "codec.pth"))
conf   = os.getenv("FISH_DECODER_CONFIG", "modded_dac_vq")

cmd = [
    sys.executable, "-m", "tools.api_server",
    "--listen", listen,
    "--llama-checkpoint-path", str(Path(ckpt)),
    "--decoder-checkpoint-path", str(Path(codec)),
    "--decoder-config-name", conf,
]

print("[fish] cwd =", OA)
print("[fish] cmd =", cmd)

# Ejecuta en primer plano y conserva el proceso para honcho
rc = subprocess.call(cmd, cwd=str(OA))
sys.exit(rc)
