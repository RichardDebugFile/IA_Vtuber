import base64
import os
import sys
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from src.server import app

class DummyConv:
    async def ask(self, text: str, user: str = "local"):
        return "hola", "happy"

# Replace real conversation client with dummy
app.dependency_overrides = {}
import src.server as server_module
server_module.conv_client = DummyConv()

client = TestClient(app)

def test_speak_endpoint():
    resp = client.post("/speak", json={"text": "hola"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "hola"
    assert data["emotion"] == "happy"
    audio = base64.b64decode(data["audio_b64"])  # should start with our placeholder
    assert audio.startswith(b"[cheerful]")
