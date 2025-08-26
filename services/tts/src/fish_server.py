# services/tts/src/fish_server.py
from __future__ import annotations

import os
import sys
import time
import json
import subprocess
from dataclasses import dataclass
from typing import Optional, IO
from pathlib import Path

# Carga .env (services/tts/.env o raíz del repo)
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)
    found = find_dotenv(filename=".env", usecwd=True)
    if found:
        load_dotenv(found, override=False)
except Exception:
    pass

import httpx

class FishServerError(Exception): ...
class MissingCheckpointError(FishServerError): ...
class ServerStartError(FishServerError): ...
class HealthCheckError(FishServerError): ...

# pidfile por defecto dentro del proyecto
_DEFAULT_PIDFILE = str((Path(__file__).resolve().parents[1] / ".run" / "fish_api.pid"))

@dataclass
class FishServerConfig:
    repo_dir: str
    venv_python: str
    ckpt_dir: str
    host: str = "127.0.0.1"
    port: int = 8080
    decoder_config: str = "modded_dac_vq"
    start_timeout_s: int = 180
    log_path: Optional[str] = None
    pidfile: str = _DEFAULT_PIDFILE

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

class FishServerManager:
    def __init__(self, cfg: FishServerConfig) -> None:
        self.cfg = cfg
        self._proc: Optional[subprocess.Popen] = None
        self._log_fp: Optional[IO[bytes]] = None  # mantenemos abierto el archivo de log

    # ---------- utilidades ----------
    def _ckpt_ok(self) -> None:
        cfg = self.cfg
        if not os.path.isdir(cfg.ckpt_dir):
            raise MissingCheckpointError(f"No existe el directorio de checkpoint: {cfg.ckpt_dir}")
        codec = os.path.join(cfg.ckpt_dir, "codec.pth")
        conf = os.path.join(cfg.ckpt_dir, "config.json")
        if not os.path.isfile(codec) or not os.path.isfile(conf):
            raise MissingCheckpointError(f"Faltan archivos en {cfg.ckpt_dir}: codec.pth y/o config.json")

    def _open_log(self) -> Optional[IO[bytes]]:
        if not self.cfg.log_path:
            return None
        p = Path(self.cfg.log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._log_fp = open(p, "ab", buffering=0)
        return self._log_fp

    def _write_pidfile(self, pid: int) -> None:
        p = Path(self.cfg.pidfile)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(pid), encoding="utf-8")

    def _read_pidfile(self) -> Optional[int]:
        p = Path(self.cfg.pidfile)
        if not p.exists():
            return None
        try:
            return int(p.read_text(encoding="utf-8").strip())
        except Exception:
            return None

    def _remove_pidfile(self) -> None:
        p = Path(self.cfg.pidfile)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    # ---------- health ----------
    def is_alive(self) -> bool:
        url_candidates = [f"{self.cfg.base_url}/v1/health", f"{self.cfg.base_url}/health"]
        try:
            with httpx.Client(timeout=2.0) as c:
                for u in url_candidates:
                    r = c.get(u)
                    if r.status_code == 200:
                        try:
                            data = r.json()
                        except json.JSONDecodeError:
                            data = {}
                        if data.get("status") == "ok" or data.get("ok") is True:
                            return True
        except Exception:
            return False
        return False

    def wait_ready(self, timeout_s: Optional[int] = None) -> None:
        timeout = timeout_s or self.cfg.start_timeout_s
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.is_alive():
                return
            time.sleep(1.0)
        raise HealthCheckError(f"El server no respondió /health tras {timeout} s")

    # ---------- ciclo de vida ----------
    def start(self) -> int:
        if self.is_alive():
            return -1  # ya estaba vivo

        self._ckpt_ok()

        args = [
            self.cfg.venv_python, "-m", "tools.api_server",
            "--listen", f"{self.cfg.host}:{self.cfg.port}",
            "--llama-checkpoint-path", self.cfg.ckpt_dir,
            "--decoder-checkpoint-path", os.path.join(self.cfg.ckpt_dir, "codec.pth"),
            "--decoder-config-name", self.cfg.decoder_config,
        ]

        log_fp = self._open_log()

        try:
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            self._proc = subprocess.Popen(
                args,
                cwd=self.cfg.repo_dir,
                stdout=log_fp if log_fp is not None else None,
                stderr=log_fp if log_fp is not None else None,
                creationflags=creationflags,
            )
        except FileNotFoundError as e:
            raise ServerStartError("No pude lanzar python del venv (.fs). Verifica cfg.venv_python") from e
        except Exception as e:
            raise ServerStartError(f"Fallo al lanzar api_server: {e}") from e

        # Guardamos PID y esperamos health
        self._write_pidfile(self._proc.pid)
        self.wait_ready()
        return self._proc.pid

    def _kill_pid(self, pid: int) -> None:
        if os.name == "nt":
            # mata árbol de procesos
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, 15)

    def stop(self) -> None:
        # Si lo lanzamos en este proceso, cerramos por handle:
        if self._proc is not None:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            finally:
                self._proc = None

        # Extra: si existe pidfile, lo usamos para matar aunque no tengamos handle
        pid = self._read_pidfile()
        if pid:
            try:
                self._kill_pid(pid)
            except Exception:
                pass
            self._remove_pidfile()

        if self._log_fp is not None:
            try:
                self._log_fp.close()
            finally:
                self._log_fp = None

# ---------- CLI ----------
def _parse_args(argv: list[str]) -> dict:
    import argparse
    p = argparse.ArgumentParser(description="Gestor local de fish-speech api_server")

    # Ahora NO son obligatorios: toman de .env si faltan
    p.add_argument("--repo", default=os.getenv("FISH_REPO", ""), help="Ruta al repo fish-speech")
    p.add_argument("--venv-python", default=os.getenv("FISH_VENV_PY", ""), help="Ruta a python.exe del venv .fs")
    p.add_argument("--ckpt", default=os.getenv("FISH_CKPT", ""), help="Ruta al checkpoint openaudio-s1-mini")

    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--log", default=str(Path(__file__).resolve().parents[1] / ".logs" / "fish_api.log"))
    p.add_argument("--pidfile", default=_DEFAULT_PIDFILE)

    p.add_argument("--start", action="store_true", help="Arranca el server")
    p.add_argument("--stop", action="store_true", help="Detiene el server (usa pidfile si existe)")
    p.add_argument("--status", action="store_true", help="Muestra estado /health")
    return vars(p.parse_args(argv))

def main(argv: Optional[list[str]] = None) -> None:
    args = _parse_args(argv or sys.argv[1:])
    cfg = FishServerConfig(
        repo_dir=args["repo"],
        venv_python=args["venv_python"],
        ckpt_dir=args["ckpt"],
        host=args["host"],
        port=args["port"],
        log_path=args["log"],
        pidfile=args["pidfile"],
    )
    mgr = FishServerManager(cfg)

    if args["status"]:
        print("alive" if mgr.is_alive() else "down")

    if args["start"]:
        # Validación mínima para start
        if not (cfg.repo_dir and cfg.venv_python and cfg.ckpt_dir):
            print("[ERROR] Faltan rutas (--repo/--venv-python/--ckpt o variables FISH_REPO/FISH_VENV_PY/FISH_CKPT).", file=sys.stderr)
            sys.exit(2)
        try:
            pid = mgr.start()
            msg = "arrancado (nuevo)" if pid != -1 else "ya estaba arriba"
            print(f"Server {msg}. URL: {cfg.base_url}")
        except FishServerError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(2)

    if args["stop"]:
        mgr.stop()
        print("stop: ok")

if __name__ == "__main__":
    main()
