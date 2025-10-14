#!/usr/bin/env python3
"""Utilities for running the tides web application server."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import threading
import time
from contextlib import suppress
from typing import Optional, Tuple

from src.tides_web.app import application
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server


HOST = "127.0.0.1"
PORT = 8000
_SHUTDOWN_POLL_INTERVAL = 0.1


class SilentWSGIRequestHandler(WSGIRequestHandler):
    """WSGI request handler that suppresses access logging."""

    def log_message(self, format: str, *args) -> None:  # noqa: D401, A003 - signature fixed by base class
        pass


def _port_in_use(host: str, port: int) -> bool:
    """Return True if something is currently listening on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _find_pids_for_port(port: int) -> set[int]:
    """Use system tools (lsof/fuser) to discover process IDs bound to the port."""
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
                check=False,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
        for token in result.stdout.replace(":", " ").split():
            token = token.strip()
            if token.isdigit():
                pids.add(int(token))
    return pids


def _terminate_process(pid: int, host: str, port: int, timeout: float) -> None:
    """Send polite then forceful signals to the process occupying the port."""
    if pid == os.getpid():
        return
    for sig in (signal.SIGTERM, getattr(signal, "SIGKILL", None)):
        if sig is None:
            continue
        with suppress(ProcessLookupError, PermissionError):
            os.kill(pid, sig)
        deadline = time.time() + timeout
        while _port_in_use(host, port) and time.time() < deadline:
            time.sleep(_SHUTDOWN_POLL_INTERVAL)
        if not _port_in_use(host, port):
            return


def ensure_port_available(host: str, port: int, timeout: float = 5.0) -> None:
    """Free host:port by terminating any existing listeners.

    Raises:
        RuntimeError: If the port remains busy after best-effort termination.
    """
    if not _port_in_use(host, port):
        return
    pids = _find_pids_for_port(port)
    if not pids:
        raise RuntimeError(f"Port {port} is already in use.")
    for pid in pids:
        _terminate_process(pid, host, port, timeout)
        if not _port_in_use(host, port):
            return
    if _port_in_use(host, port):
        raise RuntimeError(f"Port {port} could not be freed.")


def create_server(host: str = HOST, port: int = PORT) -> WSGIServer:
    """Return a configured WSGI HTTP server instance."""
    ensure_port_available(host, port)
    server = make_server(host, port, application, handler_class=SilentWSGIRequestHandler)
    server.daemon_threads = True  # type: ignore[attr-defined]
    return server


def start_server(
    host: str = HOST,
    port: int = PORT,
    background: bool = False,
) -> Tuple[WSGIServer, Optional[threading.Thread]]:
    ...
    """Start the web server.

    Args:
        host: Interface to bind.
        port: Port to listen on.
        background: If True, run the server in a daemon thread. The caller is
            responsible for keeping the main program alive.

    Returns:
        Tuple of (server, thread). The thread is None when running in the foreground.
    """
    httpd = create_server(host, port)
    if background:
        thread = threading.Thread(
            target=httpd.serve_forever,
            name="tides-web-server",
            daemon=True,
        )
        thread.start()
        return httpd, thread

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        with suppress(Exception):
            httpd.server_close()
    return httpd, None


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the tides web application server.")
    parser.add_argument("--host", default=HOST, help="Interface to bind (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=PORT, help="Port to bind (default 8000)")
    parser.add_argument(
        "--background",
        action="store_true",
        help="Run the server in a background daemon thread.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    server, thread = start_server(args.host, args.port, background=args.background)
    if thread is not None:
        try:
            thread.join()
        except KeyboardInterrupt:
            pass
        finally:
            with suppress(Exception):
                server.shutdown()  # type: ignore[attr-defined]
            with suppress(Exception):
                server.server_close()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
