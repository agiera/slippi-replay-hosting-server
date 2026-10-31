"""StreamChangeNotifier bridges Postgres NOTIFY (listener thread) to asyncio waiters."""
import asyncio
import threading
import time

import pytest

from app.services.stream_notify import StreamChangeNotifier


@pytest.fixture()
def listening_notifier(monkeypatch):
    # Pretend the LISTEN thread is up so wait_for_change blocks on real wakeups.
    notifier = StreamChangeNotifier(fallback_interval=0.01)
    monkeypatch.setattr(StreamChangeNotifier, "listening", property(lambda self: True))
    return notifier


def test_wake_from_listener_thread_resolves_pending_waiter(listening_notifier):
    async def scenario():
        waiter = asyncio.ensure_future(listening_notifier.wait_for_change(timeout=5.0))
        await asyncio.sleep(0)  # let the waiter register itself
        threading.Timer(0.05, listening_notifier._wake_all).start()
        started = time.monotonic()
        result = await waiter
        return result, time.monotonic() - started

    notified, elapsed = asyncio.run(scenario())
    assert notified is True
    assert elapsed < 1.0


def test_wake_resolves_every_concurrent_waiter_once(listening_notifier):
    async def scenario():
        waiters = [asyncio.ensure_future(listening_notifier.wait_for_change(timeout=5.0)) for _ in range(3)]
        await asyncio.sleep(0)
        threading.Timer(0.02, listening_notifier._wake_all).start()
        return await asyncio.gather(*waiters)

    assert asyncio.run(scenario()) == [True, True, True]
    assert listening_notifier._waiters == set()


def test_timeout_without_notification_returns_false(listening_notifier):
    async def scenario():
        started = time.monotonic()
        result = await listening_notifier.wait_for_change(timeout=0.05)
        return result, time.monotonic() - started

    notified, elapsed = asyncio.run(scenario())
    assert notified is False
    assert 0.04 <= elapsed < 1.0
    assert listening_notifier._waiters == set()


def test_without_listener_falls_back_to_bounded_sleep():
    notifier = StreamChangeNotifier(fallback_interval=0.02)
    assert notifier.listening is False

    async def scenario():
        started = time.monotonic()
        result = await notifier.wait_for_change(timeout=30.0)
        return result, time.monotonic() - started

    notified, elapsed = asyncio.run(scenario())
    assert notified is False
    # Bounded by fallback_interval, not by the (long) heartbeat timeout.
    assert elapsed < 1.0


def test_start_is_a_noop_on_non_postgres_urls(monkeypatch):
    from app.services import stream_notify

    monkeypatch.setattr(stream_notify.settings, "DATABASE_URL", "sqlite:///./x.db")
    notifier = StreamChangeNotifier()
    notifier.start()
    assert notifier.listening is False
    notifier.stop()


def test_stop_wakes_waiters_so_sse_loops_can_exit(listening_notifier):
    async def scenario():
        waiter = asyncio.ensure_future(listening_notifier.wait_for_change(timeout=5.0))
        await asyncio.sleep(0)
        threading.Timer(0.02, listening_notifier.stop).start()
        return await waiter

    assert asyncio.run(scenario()) is True
