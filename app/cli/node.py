import os
import sys
import subprocess
import signal

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
PID_FILE = os.path.join(BASE_DIR, "node.pid")
LOG_FILE = os.path.join(BASE_DIR, "debug.log")

def start():
    if os.path.exists(PID_FILE):
        print("[!] Node already running.")
        return

    log = open(LOG_FILE, "w")
    process = subprocess.Popen(
        [sys.executable, "-c", "from lib.node.server import run_server; run_server()"],
        stdout=log,
        stderr=log,
        cwd=BASE_DIR,
        env={**os.environ, "PYTHONPATH": BASE_DIR}
    )

    with open(PID_FILE, "w") as f:
        f.write(str(process.pid))

    print(f"[+] Node started (PID: {process.pid}) - log: {LOG_FILE}")

def stop():
    if not os.path.exists(PID_FILE):
        print("[!] Process not found.")
        return

    with open(PID_FILE, "r") as f:
        pid = int(f.read().strip())

    try:
        os.kill(pid, signal.SIGTERM)
        print("[-] Node stopped.")
    except ProcessLookupError:
        print("[!] Process not found.")
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
            os.remove(LOG_FILE)
            print("[cleanup] Cleaned up PID and log files.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.cli.node [start|stop]")
    elif sys.argv[1] == "start":
        start()
    elif sys.argv[1] == "stop":
        stop()
    else:
        print("Unknown command.")
