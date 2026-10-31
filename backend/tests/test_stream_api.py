"""The API reads live-stream state written by the (separate) FTP process."""
import asyncio
import json
import time

import pytest

from app.api.v1 import replays as replays_api
from app.services import stream_state
from app.services.stream_notify import stream_change_notifier


@pytest.fixture(autouse=True)
def _stream_state_on_test_db(stream_state_db):
    stream_state.clear_all()


@pytest.fixture(autouse=True)
def _fast_fallback(monkeypatch):
    # No LISTEN thread under SQLite; make the degraded refresh interval tiny.
    monkeypatch.setattr(stream_change_notifier, "_fallback_interval", 0.01)


class _FakeRequest:
    def __init__(self, last_event_id: int | None = None) -> None:
        self.headers = {"last-event-id": str(last_event_id)} if last_event_id is not None else {}
        self.disconnected = False

    async def is_disconnected(self) -> bool:
        return self.disconnected


def _parse_sse(chunk: str) -> dict:
    event: dict = {}
    for line in chunk.strip().splitlines():
        key, _, value = line.partition(": ")
        event[key] = json.loads(value) if key == "data" else value
    return event


async def _collect(request: _FakeRequest, db_session, *, until, timeout: float = 3.0) -> list[dict]:
    response = await replays_api.stream_events(request=request, db=db_session, tournament_id=None)
    events: list[dict] = []
    deadline = time.monotonic() + timeout

    async def consume():
        async for chunk in response.body_iterator:
            events.append(_parse_sse(chunk))
            if until(events):
                request.disconnected = True

    try:
        await asyncio.wait_for(consume(), timeout=deadline - time.monotonic())
    except asyncio.TimeoutError:
        pytest.fail(f"SSE stream did not satisfy condition; got {[e.get('event') for e in events]}")
    return events


def test_sse_snapshot_then_pushes_ftp_writes_as_events(db_session):
    stream_state.set_source_connection_state("WII-S", "u", {"public"}, connected=True)
    stream_state.set_source_player_preview("WII-S", [{"port": 1, "display_name": "Alice"}], stage=31)

    async def scenario():
        request = _FakeRequest()

        async def writer():
            # The "FTP process" writes a moment after the client is subscribed.
            await asyncio.sleep(0.05)
            await asyncio.to_thread(stream_state.record_stream_event, "WII-S", "u", "public", "g.slp", "ended")

        asyncio.ensure_future(writer())
        return await _collect(
            request,
            db_session,
            until=lambda evs: any(e.get("event") == "stream_event" and e["data"]["status"] == "ended" for e in evs),
        )

    events = asyncio.run(scenario())

    snapshot = events[0]
    assert snapshot["event"] == "snapshot"
    assert snapshot["data"]["sources"][0]["source_name"] == "WII-S"
    assert snapshot["data"]["sources"][0]["player_preview"][0]["display_name"] == "Alice"
    assert snapshot["data"]["sources"][0]["stage_preview"] == 31

    pushed = [e for e in events if e.get("event") == "stream_event"]
    assert pushed[-1]["data"]["status"] == "ended"
    assert pushed[-1]["id"] == str(pushed[-1]["data"]["event_id"])

    # The connection row changed too (stream_phase), so a status frame follows.
    statuses = [e for e in events if e.get("event") == "status"]
    assert statuses and statuses[-1]["data"]["sources"][0]["stream_phase"] == "ended"


def test_sse_resumes_from_last_event_id_without_replaying(db_session):
    stream_state.set_source_connection_state("WII-R", "u", {"public"}, connected=True)
    first = stream_state.record_stream_event("WII-R", "u", "public", "", "started")
    second = stream_state.record_stream_event("WII-R", "u", "public", "a.slp", "completed")

    async def scenario():
        request = _FakeRequest(last_event_id=first["event_id"])

        async def writer():
            await asyncio.sleep(0.05)
            await asyncio.to_thread(stream_state.record_stream_event, "WII-R", "u", "public", "a.slp", "ended")

        asyncio.ensure_future(writer())
        return await _collect(
            request,
            db_session,
            until=lambda evs: any(e.get("event") == "stream_event" and e["data"]["status"] == "ended" for e in evs),
        )

    events = asyncio.run(scenario())
    pushed_ids = [e["data"]["event_id"] for e in events if e.get("event") == "stream_event"]
    # The snapshot already carried `second`; the cursor moves past it, so only
    # the new "ended" event is streamed - never `first`.
    assert first["event_id"] not in pushed_ids
    assert second["event_id"] not in pushed_ids
    assert len(pushed_ids) == 1


def test_sse_stops_when_client_disconnects(db_session):
    async def scenario():
        request = _FakeRequest()
        response = await replays_api.stream_events(request=request, db=db_session, tournament_id=None)
        iterator = response.body_iterator
        first = await iterator.__anext__()
        request.disconnected = True
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(iterator.__anext__(), timeout=2.0)
        return first

    assert asyncio.run(scenario()).startswith("event: snapshot")


def test_live_download_serves_staged_file_from_shared_volume(client, monkeypatch, tmp_path):
    staging = tmp_path / "ftp-staging"
    staged = staging / "agiera" / "sess" / "public" / "live.slp"
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b"{U\x03raw[$U#l\x00\x00\x00\x10" + b"\x36" * 16)
    monkeypatch.setattr(replays_api.settings, "FTP_STAGING_DIR", str(staging))

    stream_state.set_source_connection_state("WII-L", "u", {"public"}, connected=True)

    assert client.get("/api/v1/replays/stream/sources/WII-L/download").status_code == 404

    # FTP process marks the STOR target; the API can now stream it mid-upload.
    stream_state.set_source_active_staged_file("WII-L", str(staged))
    res = client.get("/api/v1/replays/stream/sources/WII-L/download")
    assert res.status_code == 200
    assert res.content == staged.read_bytes()
    assert res.headers["content-type"].startswith("application/x-slippi-replay")

    stream_state.set_source_active_staged_file("WII-L", None)
    assert client.get("/api/v1/replays/stream/sources/WII-L/download").status_code == 404


def test_live_download_rejects_paths_outside_staging_root(client, monkeypatch, tmp_path):
    monkeypatch.setattr(replays_api.settings, "FTP_STAGING_DIR", str(tmp_path / "ftp-staging"))
    outside = tmp_path / "elsewhere.slp"
    outside.write_bytes(b"x")

    stream_state.set_source_connection_state("WII-P", "u", {"public"}, connected=True)
    stream_state.set_source_active_staged_file("WII-P", str(outside))

    assert client.get("/api/v1/replays/stream/sources/WII-P/download").status_code == 400


def test_stream_status_endpoint_reads_shared_state(client):
    stream_state.set_source_connection_state("WII-T", "u", {"public"}, connected=True)
    stream_state.set_source_player_preview(
        "WII-T",
        [{"port": 1, "display_name": "Bob", "character_id": 9, "type": 0, "is_cpu": False}],
        stage=8,
    )
    stream_state.record_stream_event("WII-T", "u", "public", "", "started")

    body = client.get("/api/v1/replays/stream/status").json()
    source = next(s for s in body["sources"] if s["source_name"] == "WII-T")
    assert source["connected"] is True
    assert source["stream_phase"] == "started"
    assert source["stage_preview"] == 8
    assert source["player_preview"][0]["name"] == "Bob"
    assert [e["status"] for e in body["events"] if e["source_name"] == "WII-T"] == ["started"]
