"""Standalone FTP ingest process.

Runs pyftpdlib in the foreground, separate from the API so that API hot-reloads
and restarts never drop in-flight replay uploads. State is shared through
Postgres (see ``app.services.stream_state``).

    python -m app.ftp_main
"""
from __future__ import annotations

import signal
import threading

from app.services.ftp_server import start_ftp_server, stop_ftp_server


def main() -> None:
    stop = threading.Event()

    def _handle_signal(signum, _frame) -> None:
        print(f"[FTP] Received signal {signum}; shutting down", flush=True)
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    start_ftp_server()
    try:
        stop.wait()
    finally:
        stop_ftp_server()


if __name__ == "__main__":
    main()
