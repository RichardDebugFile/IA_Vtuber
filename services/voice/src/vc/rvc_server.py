# services/voice/src/vc/rvc_server.py
from __future__ import annotations
import os, io, argparse, logging
import numpy as np
import soundfile as sf
from fastapi import FastAPI, UploadFile, File, Form, Response
from fastapi.responses import JSONResponse
import uvicorn

log = logging.getLogger("rvc_server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RVC Local Bridge", version="0.2")

# -------------- utilidades --------------

def _to_mono(y: np.ndarray) -> np.ndarray:
    if getattr(y, "ndim", 1) == 2:
        y = y.mean(axis=1)
    return y.astype(np.float32, copy=False)

def _resample_linear(y: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return y.astype(np.float32, copy=False)
    n_out = int(round(len(y) * sr_out / sr_in))
    if n_out <= 1:
        return y.astype(np.float32, copy=False)
    x_old = np.linspace(0.0, 1.0, len(y), endpoint=False)
    x_new = np.linspace(0.0, 1.0, n_out, endpoint=False)
    return np.interp(x_new, x_old, y).astype(np.float32)

def _analyze(y: np.ndarray) -> tuple[float, float, float]:
    if len(y) == 0:
        return 0.0, 0.0, 0.0
    rms = float(np.sqrt(np.mean(y**2)))
    return rms, float(y.min()), float(y.max())

# -------------- backends --------------

def _convert_passthrough(y: np.ndarray, sr_in: int, target_sr: int, volume: float) -> tuple[np.ndarray, int]:
    """Sin conversión; solo resample + ganancia. Útil como fallback/diagnóstico."""
    y2 = _resample_linear(_to_mono(y), sr_in, target_sr)
    y2 = np.clip(y2 * float(volume), -1.0, 1.0).astype(np.float32)
    return y2, target_sr

def _convert_device(y: np.ndarray, sr_in: int, *, volume: float) -> tuple[np.ndarray, int]:
    """
    Reproduce a través de Cable (PLAY_TO) y graba loopback del dispositivo TAP_FROM
    mientras la GUI de w-Okada hace la conversión en vivo.

    Env:
      RVC_PLAY_TO (default: 'CABLE Input (VB-Audio Virtual Cable)')
      RVC_TAP_FROM (default: 'CABLE Output (VB-Audio Virtual Cable)')
      RVC_SR (default: 48000)
      RVC_PAD_MS (default: 180)
    """
    try:
        import soundcard as sc  # puede no estar instalado
    except Exception as e:
        raise RuntimeError(f"soundcard no disponible: {e}")

    play_name = os.getenv("RVC_PLAY_TO", "CABLE Input (VB-Audio Virtual Cable)")
    # IMPORTANTE: para tap debes usar *Output* (o 'CABLE B Output ...'), no *Input*.
    tap_name  = os.getenv("RVC_TAP_FROM", "CABLE Output (VB-Audio Virtual Cable)")
    target_sr = int(os.getenv("RVC_SR", "48000"))
    pad_ms    = int(os.getenv("RVC_PAD_MS", "180"))

    # Buscar speaker de reproducción exacto
    speaker_play = None
    for spk in sc.all_speakers():
        if spk.name == play_name:
            speaker_play = spk
            break
    if speaker_play is None:
        names = [s.name for s in sc.all_speakers()]
        raise RuntimeError(f"No se encontró speaker de reproducción '{play_name}'. Disponibles: {names}")

    # El tap usa get_microphone con include_loopback=True
    mic_loop = sc.get_microphone(tap_name, include_loopback=True)
    if mic_loop is None:
        raise RuntimeError(f"No se encontró dispositivo de loopback/mic '{tap_name}'")

    y_mono = _to_mono(y)
    y48 = _resample_linear(y_mono, sr_in, target_sr)
    y48 = np.clip(y48 * float(volume), -1.0, 1.0).astype(np.float32)

    dur_s = len(y48) / float(target_sr)
    total_frames = int((dur_s + pad_ms / 1000.0) * target_sr)

    rec = None
    recorded = None
    try:
        rec = mic_loop.recorder(samplerate=target_sr)
        rec.__enter__()
        _ = rec.record(int(0.05 * target_sr))  # preroll

        with speaker_play.player(samplerate=target_sr) as player:
            player.play(y48)                       # reproducimos el TTS
            recorded = rec.record(total_frames)    # capturamos la salida convertida

        post = rec.record(int(0.05 * target_sr))   # postroll
        recorded = np.concatenate([recorded, post], axis=0)
    finally:
        if rec is not None:
            rec.__exit__(None, None, None)

    if getattr(recorded, "ndim", 1) == 2:
        recorded = recorded.mean(axis=1).astype(np.float32)

    # Recorte simple de extremos silenciosos
    thr = 1e-4
    nz = np.flatnonzero(np.abs(recorded) > thr)
    if nz.size >= 2:
        recorded = recorded[nz[0]: nz[-1] + 1]

    return recorded.astype(np.float32), target_sr

# -------------- FastAPI --------------

@app.get("/health")
def health():
    return {
        "ok": True,
        "backend_default": os.getenv("RVC_BACKEND", "device"),
        "play_to": os.getenv("RVC_PLAY_TO", "CABLE Input (VB-Audio Virtual Cable)"),
        "tap_from": os.getenv("RVC_TAP_FROM", "CABLE Output (VB-Audio Virtual Cable)"),
    }

# Compatible con tu .env: RVC_HTTP_CONVERT_PATH=/v1/voice/convert
@app.post("/v1/voice/convert")
async def convert_voice(
    file: UploadFile = File(...),
    key: str = Form("0"),
    f0: str = Form("rmvpe"),
    index_rate: str = Form("0.66"),
    volume: str = Form("1.0"),
    sr: str = Form("24000"),
    model: str = Form(""),
    index: str = Form(""),
):
    """
    Recibe WAV y devuelve WAV.
    - backend por defecto: 'device' (GUI w-Okada + VB-Cable).
    - fallback automático a 'passthrough' si falla device/soundcard.
    """
    try:
        raw = await file.read()
        try:
            y_in, sr_in = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
        except Exception as e:
            return JSONResponse({"error": f"bad wav: {e}"}, status_code=400)

        try:
            target_sr = int(sr) if sr else sr_in
        except Exception:
            target_sr = sr_in

        try:
            vol = float(volume)
        except Exception:
            vol = 1.0

        backend = os.getenv("RVC_BACKEND", "device").lower().strip()
        y_out, sr_out = None, target_sr

        if backend == "passthrough":
            y_out, sr_out = _convert_passthrough(y_in, sr_in, target_sr, vol)
            mode = "passthrough"
        else:
            try:
                y_out, sr_out = _convert_device(y_in, sr_in, volume=vol)
                mode = "device"
            except Exception as dev_err:
                log.warning("Backend 'device' falló (%s). Fallback a 'passthrough'.", dev_err)
                y_out, sr_out = _convert_passthrough(y_in, sr_in, target_sr, vol)
                mode = "passthrough"

        rms, vmin, vmax = _analyze(y_out)
        log.info("VC %s: len=%d, sr_in=%d -> sr_out=%d, vol=%.3f, rms=%.6f, min=%.3f, max=%.3f",
                 mode, len(y_out), sr_in, sr_out, vol, rms, vmin, vmax)

        buf = io.BytesIO()
        sf.write(buf, y_out, sr_out, format="WAV")
        buf.seek(0)
        return Response(content=buf.getvalue(), media_type="audio/wav")

    except Exception as e:
        log.exception("Error en /v1/voice/convert")
        return JSONResponse({"error": repr(e)}, status_code=500)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=18888)
    args = ap.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
