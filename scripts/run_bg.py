
import argparse, subprocess, sys, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pidfile", required=True)
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--log", default=None)
    # Captura TODO lo que venga tras el '--' estándar de shell
    ap.add_argument("cmd", nargs=argparse.REMAINDER, help="command to run (prefix with --)")
    args = ap.parse_args()

    if not args.cmd:
        ap.error("missing command. Usage: run_bg.py --pidfile ... [--cwd ...] [--log ...] -- <cmd ...>")

    # El primer token suele ser el propio '--', descártalo si aparece
    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    if not cmd:
        ap.error("empty command after '--'")

    # Log
    logfh = None
    if args.log:
        os.makedirs(os.path.dirname(args.log), exist_ok=True)
        logfh = open(args.log, "ab", buffering=0)

    # Lanzar en background
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    p = subprocess.Popen(
        cmd,
        cwd=args.cwd,
        stdout=logfh or subprocess.DEVNULL,
        stderr=logfh or subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        shell=False
    )

    os.makedirs(os.path.dirname(args.pidfile), exist_ok=True)
    with open(args.pidfile, "w", encoding="utf-8") as f:
        f.write(str(p.pid))

    print(f"Started: {' '.join(cmd)} (pid={p.pid})")

if __name__ == "__main__":
    main()
