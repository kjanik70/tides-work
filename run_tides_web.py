#!/usr/bin/env python3
"""Run the small tides web app for local testing."""
from src.tides_web.app import application
from wsgiref.simple_server import make_server
import os
import signal
import socket
import subprocess
import time


HOST = "127.0.0.1"
PORT = 8000


def _port_in_use(host: str, port: int) -> bool:
    """Return True if something is currently listening on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _find_pids_for_port(port: int) -> set[int]:
    """Use system tools (lsof/fuser) to discover PIDs bound to the port."""
    commands = (
        ["lsof", "-t", f"-iTCP:{port}"],
        ["lsof", "-t", f"-i:{port}"],
        ["fuser", f"{port}/tcp"],
    )
    pids: set[int] = set()
    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2,
            )
        except FileNotFoundError:
            continue
        except subprocess.SubprocessError:
            continue
        output = result.stdout.strip()
        if not output:
            continue
        for token in output.replace(":", " ").split():
            token = token.strip()
            if token.isdigit():
                pids.add(int(token))
    return pids


def _terminate_process(pid: int) -> None:
    """Send polite then forceful signals to the process."""
    if pid == os.getpid():
        return
    for sig in (signal.SIGTERM, getattr(signal, "SIGKILL", None)):
        if sig is None:
            continue
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return
        except PermissionError:
            return
        if sig == signal.SIGTERM:
            time.sleep(0.2)
            if not _port_in_use(HOST, PORT):
                return


def ensure_port_available(host: str, port: int, timeout: float = 5.0) -> None:
    """Free host:port by terminating any existing listeners."""
    if not _port_in_use(host, port):
        return
    print(f"Port {port} already in use; attempting to stop existing listener...")
    pids = _find_pids_for_port(port)
    if not pids:
        raise SystemExit(
            f"Could not identify process using port {port}. "
            "Stop it manually and rerun."
        )
    for pid in pids:
        _terminate_process(pid)
    deadline = time.time() + timeout
    while _port_in_use(host, port) and time.time() < deadline:
        time.sleep(0.1)
    if _port_in_use(host, port):
        raise SystemExit(f"Port {port} is still busy; aborting.")


def main() -> None:
    ensure_port_available(HOST, PORT)
    print(f"Serving on http://{HOST}:{PORT}")
    with make_server(HOST, PORT, application) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
