import os, subprocess, time, requests, sys

ROOT = os.path.dirname(os.path.dirname(__file__))

def ok(url):
    try:
        return requests.get(url, timeout=2).ok
    except Exception:
        return False

def run_all():
    # 1) Fish
    if not ok("http://127.0.0.1:9080/"):
        fish = [
            sys.executable, "-m", "tools.api_server",
            "--listen", "127.0.0.1:9080",
            "--llama-checkpoint-path", os.path.join(ROOT,"services","voice","checkpoints","openaudio-s1-mini"),
            "--decoder-checkpoint-path", os.path.join(ROOT,"services","voice","checkpoints","openaudio-s1-mini","codec.pth"),
            "--decoder-config-name", "modded_dac_vq",
        ]
        subprocess.Popen(fish, cwd=ROOT)
        print("Fish iniciado...")
    else:
        print("Fish ya estaba corriendo.")

    # 2) w-okada
    if not ok("http://127.0.0.1:18888/"):
        ps1 = os.path.join(ROOT, "scripts", "wokada_start.ps1")
        subprocess.Popen(["powershell","-ExecutionPolicy","Bypass","-File",ps1], cwd=ROOT)
        print("w-okada iniciado...")
    else:
        print("w-okada ya estaba corriendo.")

    # 3) voice
    time.sleep(3)
    svc = [
        sys.executable, "-m", "uvicorn", "src.server:app",
        "--host","127.0.0.1","--port","8810","--app-dir","services/voice/src"
    ]
    subprocess.Popen(svc, cwd=ROOT)
    print("voice iniciado en :8810")

if __name__ == "__main__":
    run_all()
