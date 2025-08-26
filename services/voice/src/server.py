from fastapi import FastAPI, Response, Header
from fastapi.responses import FileResponse, JSONResponse
from .config import SETTINGS
from .schemas.speak_request import SpeakRequest
from .pipeline import run_tts_vc

app = FastAPI(title="Voice Service", version="0.1.0")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/speak")
def speak(req: SpeakRequest, accept: str = Header(default="application/json")):
    """
    POST /speak
    Body: SpeakRequest { text, emotion?, style?, rvc? }
    Respuesta:
      - si Accept: audio/wav => devuelve WAV
      - si Accept: */json    => { path, duration }
    """
    out_path, duration = run_tts_vc(
        text=req.text,
        emotion=req.emotion,
        style=req.style,
        speaker_id=req.speaker_id,
        rvc_opts=req.rvc.model_dump() if req.rvc else {"enabled": False},
        want_sr=req.sample_rate,
    )

    if "audio/wav" in accept:
        return FileResponse(out_path, media_type="audio/wav", filename="speech.wav")
    return JSONResponse({"path": out_path, "duration": duration})
