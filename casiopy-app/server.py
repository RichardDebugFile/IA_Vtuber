"""casiopy-app — Frontend web de la VTuber beta (Puerto 8830)."""
import os
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
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


# ── Proxy transparente → monitoring-service (evita CORS en el browser) ───────
_PROXY_SKIP_HEADERS = {"host", "content-length", "transfer-encoding", "connection"}

@app.api_route("/mon/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def monitoring_proxy(path: str, request: Request):
    """Reenvía /mon/** → monitoring-service, mismo origen → sin CORS."""
    url = f"{MONITORING_URL}/{path}"
    params = dict(request.query_params)
    body   = await request.body()
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in _PROXY_SKIP_HEADERS}

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.request(
            method=request.method,
            url=url,
            params=params,
            content=body or None,
            headers=headers,
        )

    # Quitar headers hop-by-hop que no deben reenviarse
    fwd_headers = {k: v for k, v in r.headers.items()
                   if k.lower() not in _PROXY_SKIP_HEADERS}
    return Response(content=r.content, status_code=r.status_code, headers=fwd_headers)


# ── SPA fallback (debe ir al final) ─────────────────────────────────────────
@app.get("/", include_in_schema=False)
@app.get("/{path:path}", include_in_schema=False)
def spa(path: str = ""):
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8830, reload=False)
