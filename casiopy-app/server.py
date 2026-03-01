"""casiopy-app — Frontend web de la VTuber beta (Puerto 8830)."""
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR      = Path(__file__).parent / "static"
GATEWAY_URL     = os.getenv("GATEWAY_URL",     "http://127.0.0.1:8800")
GATEWAY_WS      = os.getenv("GATEWAY_WS",      "ws://127.0.0.1:8800")
MONITORING_URL  = os.getenv("MONITORING_URL",  "http://127.0.0.1:8900")

app = FastAPI(title="casiopy-app", version="1.0.0", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "service": "casiopy-app", "version": "1.0.0"}


@app.get("/config")
def config():
    """Expone URLs del gateway y monitoring al frontend."""
    return {
        "gateway_url":    GATEWAY_URL,
        "gateway_ws":     GATEWAY_WS,
        "monitoring_url": MONITORING_URL,
    }


@app.get("/", include_in_schema=False)
@app.get("/{path:path}", include_in_schema=False)
def spa(path: str = ""):
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8830, reload=False)
