"""Wake SSE clients when stream state changes, via Postgres LISTEN/NOTIFY.

A single background thread per API process holds a dedicated connection with
``LISTEN stream_state``. The ``stream_state_notify`` trigger (migration 0023)
fires NOTIFY on commit for every write to the stream tables, so waiters wake
only once the change is visible and no query runs while nothing is happening.

On non-Postgres engines (SQLite tests) there is nothing to listen to, so
``wait_for_change`` simply times out after ``fallback_interval`` — the only
place a poll survives, and only as a degraded mode.
"""
from __future__ import annotations

import asyncio
import threading

import psycopg
from sqlalchemy.engine import make_url

from app.core.config import settings

NOTIFY_CHANNEL = "stream_state"


class StreamChangeNotifier:
    def __init__(self, *, fallback_interval: float = 1.0) -> None:
        self._fallback_interval = fallback_interval
        self._lock = threading.Lock()
        self._waiters: set[tuple[asyncio.AbstractEventLoop, asyncio.Future]] = set()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._conn: psycopg.Connection | None = None

    @property
    def listening(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        url = make_url(settings.DATABASE_URL)
        if url.get_backend_name() != "postgresql":
            print("[STREAM] LISTEN/NOTIFY unavailable (non-Postgres DB); SSE falls back to timed refresh", flush=True)
            return
        if self._thread is not None:
            return
        self._stop.clear()
        dsn = url.set(drivername="postgresql").render_as_string(hide_password=False)
        self._thread = threading.Thread(target=self._run, args=(dsn,), name="stream-listen", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        conn = self._conn
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._wake_all()

    # -------------------------------------------------------------------- waiting

    async def wait_for_change(self, timeout: float) -> bool:
        """Block until a NOTIFY arrives or ``timeout`` elapses. True if notified."""
        if not self.listening:
            await asyncio.sleep(min(timeout, self._fallback_interval))
            return False

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        key = (loop, future)
        with self._lock:
            self._waiters.add(key)
        try:
            await asyncio.wait_for(future, timeout)
            return True
        except (asyncio.TimeoutError, TimeoutError):
            return False
        finally:
            with self._lock:
                self._waiters.discard(key)

    def _wake_all(self) -> None:
        with self._lock:
            waiters = list(self._waiters)
            self._waiters.clear()
        for loop, future in waiters:
            loop.call_soon_threadsafe(_resolve, future)

    # ------------------------------------------------------------- listener thread

    def _run(self, dsn: str) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                with psycopg.connect(dsn, autocommit=True, application_name="slippi-stream-listen") as conn:
                    self._conn = conn
                    conn.execute(f"LISTEN {NOTIFY_CHANNEL}")
                    print(f"[STREAM] Listening on '{NOTIFY_CHANNEL}'", flush=True)
                    backoff = 1.0
                    # Wake all waiters once so clients connected during a gap resync.
                    self._wake_all()
                    while not self._stop.is_set():
                        # The timeout only bounds how often we re-check the stop flag.
                        for _ in conn.notifies(timeout=30.0):
                            self._wake_all()
            except Exception as exc:
                if self._stop.is_set():
                    break
                print(f"[STREAM] LISTEN connection lost ({exc}); retrying in {backoff:.0f}s", flush=True)
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 30.0)
            finally:
                self._conn = None


def _resolve(future: asyncio.Future) -> None:
    if not future.done():
        future.set_result(None)


stream_change_notifier = StreamChangeNotifier()
