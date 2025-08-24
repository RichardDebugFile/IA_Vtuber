
import argparse, os, signal, time, subprocess, sys

def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def terminate_pid(pid: int) -> None:
    if os.name == "nt":
        # Intenta terminar con taskkill (incluye hijos)
        subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pidfile", required=True)
    args = ap.parse_args()

    if not os.path.exists(args.pidfile):
        print(f"(pidfile no existe) {args.pidfile}")
        return

    try:
        with open(args.pidfile, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
    except Exception:
        print(f"No pude leer PID en {args.pidfile}")
        try: os.remove(args.pidfile)
        except OSError: pass
        return

    if not is_running(pid):
        print(f"(no estaba corriendo) pid={pid}")
        try: os.remove(args.pidfile)
        except OSError: pass
        return

    print(f"Terminando pid={pid} ...")
    terminate_pid(pid)

    # Pequeña espera y limpieza
    for _ in range(20):
        if not is_running(pid):
            break
        time.sleep(0.1)

    if is_running(pid):
        print("No se pudo terminar del todo (puede que sea un proceso zombie).")
    else:
        print("OK.")
        try: os.remove(args.pidfile)
        except OSError: pass

if __name__ == "__main__":
    main()
