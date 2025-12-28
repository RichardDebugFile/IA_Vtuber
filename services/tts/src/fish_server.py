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
# IMPORTANTE: override=True para que el .env tenga prioridad sobre variables del sistema
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)
    found = find_dotenv(filename=".env", usecwd=True)
    if found:
        load_dotenv(found, override=True)
except Exception:
    pass

import httpx

class FishServerError(Exception): ...
class MissingCheckpointError(FishServerError): ...
class ServerStartError(FishServerError): ...
class HealthCheckError(FishServerError): ...

_DEFAULT_PIDFILE = str((Path(__file__).resolve().parents[1] / ".run" / "fish_api.pid"))

# Encontrar la raíz del proyecto (donde está el .git o .env)
def _find_project_root() -> Path:
    """Encuentra la raíz del proyecto buscando .git o .env"""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / ".env").exists():
            return parent
    # Si no encuentra, usar 3 niveles arriba de este archivo (services/tts/src)
    return Path(__file__).resolve().parents[3]

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

    def __post_init__(self):
        """Convierte rutas relativas a absolutas basándose en la raíz del proyecto"""
        project_root = _find_project_root()

        # Convertir rutas relativas a absolutas
        if self.repo_dir and not Path(self.repo_dir).is_absolute():
            self.repo_dir = str((project_root / self.repo_dir).resolve())

        if self.venv_python and not Path(self.venv_python).is_absolute():
            self.venv_python = str((project_root / self.venv_python).resolve())

        if self.ckpt_dir and not Path(self.ckpt_dir).is_absolute():
            self.ckpt_dir = str((project_root / self.ckpt_dir).resolve())

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

class FishServerManager:
    def __init__(self, cfg: FishServerConfig) -> None:
        self.cfg = cfg
        self._proc: Optional[subprocess.Popen] = None
        self._log_fp: Optional[IO[bytes]] = None

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
        base = self.cfg.base_url
        # 1) POST /v1/health (común en builds actuales)
        try:
            with httpx.Client(timeout=2.5) as c:
                r = c.post(f"{base}/v1/health", json={})
                if r.status_code == 200:
                    try:
                        data = r.json()
                    except json.JSONDecodeError:
                        data = {}
                    if data.get("status") == "ok" or data.get("ok") is True:
                        return True
        except Exception:
            pass
        # 2) GET /v1/health
        try:
            with httpx.Client(timeout=2.0) as c:
                r = c.get(f"{base}/v1/health")
                if r.status_code == 200:
                    try:
                        data = r.json()
                    except json.JSONDecodeError:
                        data = {}
                    if data.get("status") == "ok" or data.get("ok") is True:
                        return True
        except Exception:
            pass
        # 3) GET /health
        try:
            with httpx.Client(timeout=2.0) as c:
                r = c.get(f"{base}/health")
                if r.status_code == 200:
                    try:
                        data = r.json()
                    except json.JSONDecodeError:
                        data = {}
                    if data.get("status") == "ok" or data.get("ok") is True:
                        return True
        except Exception:
            pass
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
            "--half",
        ]

        # Enable torch.compile for 10x speedup (requires PyTorch 2.0+)
        # First run takes 1-3min to compile, subsequent runs use cache
        # Set FISH_ENABLE_COMPILE=1 in .env to enable
        if os.environ.get("FISH_ENABLE_COMPILE", "").lower() in ("1", "true", "yes"):
            args.append("--compile")

        log_fp = self._open_log()

        # --- Preparar ENV para el subproceso
        env = os.environ.copy()

        # 1) Inyección del guard de VRAM via sitecustomize
        inject_dir = str(Path(__file__).parent / "pyinject")
        env["PYTHONPATH"] = inject_dir + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

        # 2) Normaliza PYTORCH_CUDA_ALLOC_CONF si viene con '=' y ';'
        alloc = env.get("PYTORCH_CUDA_ALLOC_CONF", "")
        if "max_split_size_mb=" in alloc or ";" in alloc:
            env["PYTORCH_CUDA_ALLOC_CONF"] = alloc.replace("=", ":").replace(";", ",")

        # 3) Add FFmpeg DLLs to PATH for torchcodec (Windows)
        if os.name == "nt":
            ffmpeg_dll_paths = [
                r"C:\Users\PC RYZEN  7\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-7.1.1-full_build-shared\bin",
                r"C:\ProgramData\chocolatey\bin"
            ]
            for ffmpeg_path in ffmpeg_dll_paths:
                if os.path.exists(ffmpeg_path):
                    env["PATH"] = ffmpeg_path + os.pathsep + env.get("PATH", "")
                    break

        try:
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            self._proc = subprocess.Popen(
                args,
                cwd=self.cfg.repo_dir,
                stdout=log_fp if log_fp is not None else None,
                stderr=log_fp if log_fp is not None else None,
                creationflags=creationflags,
                env=env,  # <--- usa env modificado
            )
        except FileNotFoundError as e:
            raise ServerStartError("No pude lanzar python del venv (.fs). Verifica cfg.venv_python") from e
        except Exception as e:
            raise ServerStartError(f"Fallo al lanzar api_server: {e}") from e

        self._write_pidfile(self._proc.pid)
        self.wait_ready(timeout_s=self.cfg.start_timeout_s)
        return self._proc.pid

    def _kill_pid(self, pid: int) -> None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, 15)

    def stop(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            finally:
                self._proc = None

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

    p.add_argument("--repo", default=os.getenv("FISH_REPO", ""), help="Ruta al repo fish-speech")
    p.add_argument("--venv-python", default=os.getenv("FISH_VENV_PY", ""), help="Ruta a python.exe del venv .fs")
    p.add_argument("--ckpt", default=os.getenv("FISH_CKPT", ""), help="Ruta al checkpoint openaudio-s1-mini")

    p.add_argument("--host", default=os.getenv("FISH_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("FISH_PORT", "8080")))
    p.add_argument("--timeout", type=int, default=int(os.getenv("FISH_START_TIMEOUT", "180")),
                   help="Segundos de espera para health")
    p.add_argument("--log", default=str(Path(__file__).resolve().parents[1] / ".logs" / "fish_api.log"),
                   help='Ruta de log; usa "" para imprimir en consola')
    p.add_argument("--pidfile", default=os.getenv("FISH_PIDFILE", _DEFAULT_PIDFILE))

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
        start_timeout_s=args["timeout"],
    )
    mgr = FishServerManager(cfg)

    if args["status"]:
        print("alive" if mgr.is_alive() else "down")

    if args["start"]:
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
