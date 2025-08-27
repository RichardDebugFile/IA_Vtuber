import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.server import app
import src.server as server_module

async def dummy_chat(messages, model):
    return "Hola mundo"

def dummy_classify(text: str) -> str:
    return "happy"

async def dummy_tts(text: str, emotion: str) -> str:
    return "ZmFrZV9iYXNlNjQ="  # fake_base64

async def dummy_publish(topic, data):
    return None

server_module.chat = dummy_chat
server_module.classify = dummy_classify
server_module.tts_synthesize = dummy_tts
server_module.publish = dummy_publish

client = TestClient(app)

def test_chat_returns_audio():
    resp = client.post("/chat", json={"user": "test", "text": "hola"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Hola mundo"
    assert data["emotion"] == "happy"
    assert data["audio_b64"] == "ZmFrZV9iYXNlNjQ="
