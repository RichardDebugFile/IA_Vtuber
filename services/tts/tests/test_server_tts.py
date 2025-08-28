import base64
import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sys as _sys
_sys.modules.pop("src.server", None)
_sys.modules.pop("src", None)
from src.server import app

client = TestClient(app)

def test_synthesize_endpoint():
    resp = client.post("/synthesize", json={"text": "hola", "emotion": "happy"})
    assert resp.status_code == 200
    data = resp.json()
    audio = base64.b64decode(data["audio_b64"])
    assert audio.startswith(b"(joyful) hola")
