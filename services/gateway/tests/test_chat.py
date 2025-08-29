import base64
import os
import sys
import httpx
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from src.main import app

client = TestClient(app)

class DummyAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def post(self, url, json=None):
        class Resp:
            def __init__(self, data):
                self._data = data
                self.status_code = 200

            def json(self):
                return self._data

            def raise_for_status(self):
                pass

        if url.endswith("/chat"):
            return Resp({"reply": "hola", "emotion": "happy"})
        elif url.endswith("/synthesize"):
            fake = base64.b64encode(b"audio").decode("ascii")
            return Resp({"audio_b64": fake})
        return Resp({})


def test_chat_endpoint(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", DummyAsyncClient)
    resp = client.post("/chat", json={"text": "hola"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "hola"
    assert data["emotion"] == "happy"
    assert base64.b64decode(data["audio_b64"]) == b"audio"
