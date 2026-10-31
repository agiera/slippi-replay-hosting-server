"""Stream state is DB-backed so the FTP and API processes can share it."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services import stream_state


@pytest.fixture(autouse=True)
def _stream_state_on_test_db(stream_state_db):
    stream_state.clear_all()


def test_state_written_by_one_process_is_visible_through_an_independent_engine(stream_state_db):
    # Simulates the FTP container writing and the API container reading: a
    # separate engine + sessionmaker sharing nothing but the database file.
    url = stream_state_db.kw["bind"].url
    other_process = sessionmaker(bind=create_engine(url, connect_args={"check_same_thread": False}))

    stream_state.set_source_connection_state("WII-X", "u", {"public"}, connected=True)
    stream_state.set_source_active_staged_file("WII-X", "/app/ftp-staging/s/public/live.slp")

    seen = stream_state.get_latest_connection("WII-X", session_factory=other_process)
    assert seen is not None
    assert seen["active_staged_path"] == "/app/ftp-staging/s/public/live.slp"
    assert seen["connected"] is True


def test_reconnect_supersedes_previous_connection_and_keeps_last_completed():
    first = stream_state.set_source_connection_state("WII-A", "u", {"public"}, connected=True)
    stream_state.record_stream_event("WII-A", "u", "public", "a.slp", "completed")

    second = stream_state.set_source_connection_state("WII-A", "u", {"public"}, connected=True)
    assert second != first

    latest = stream_state.get_latest_connection("WII-A")
    assert latest["upload_session_id"] == second
    assert latest["connected"] is True
    assert latest["player_preview"] == []
    # Carried over so a fresh connection is not misread as abandoned history.
    assert latest["last_completed_at"] is not None

    previous = stream_state.get_connection(first)
    assert previous["connected"] is False


def test_disconnect_closes_only_latest_and_snapshot_still_lists_recent_rows():
    stream_state.set_source_connection_state("WII-B", "u", {"public"}, connected=True)
    stream_state.set_source_player_preview("WII-B", [{"port": 1, "display_name": "P1"}], stage=8)
    stream_state.set_source_connection_state("WII-B", "u", {"public"}, connected=False)

    assert stream_state.get_latest_connection("WII-B") is None
    snapshot = stream_state.get_stream_status_snapshot({"WII-B"})
    assert len(snapshot["sources"]) == 1
    assert snapshot["sources"][0]["connected"] is False
    assert snapshot["sources"][0]["player_preview"][0]["display_name"] == "P1"


def test_session_started_without_completion_tracks_current_connection():
    stream_state.set_source_connection_state("WII-C", "u", {"public"}, connected=True)
    assert stream_state.session_started_without_completion("WII-C") is True
    stream_state.record_stream_event("WII-C", "u", "public", "c.slp", "ended")
    assert stream_state.session_started_without_completion("WII-C") is False


def test_events_are_cursor_ordered_across_sources_and_filterable():
    stream_state.set_source_connection_state("WII-D", "u", {"public"}, connected=True)
    stream_state.set_source_connection_state("WII-E", "u", {"public"}, connected=True)
    stream_state.record_stream_event("WII-D", "u", "public", "", "started")
    stream_state.record_stream_event("WII-E", "u", "public", "", "started")
    stream_state.record_stream_event("WII-D", "u", "public", "d.slp", "ended")

    everything = stream_state.get_stream_events_since(0)
    ids = [event["event_id"] for event in everything]
    assert ids == sorted(ids)
    assert [event["source_name"] for event in everything] == ["WII-D", "WII-E", "WII-D"]

    only_e = stream_state.get_stream_events_since(0, {"WII-E"})
    assert [event["status"] for event in only_e] == ["started"]

    tail = stream_state.get_stream_events_since(ids[1])
    assert [event["status"] for event in tail] == ["ended"]
    assert tail[0]["upload_session_id"] == stream_state.get_latest_connection("WII-D")["upload_session_id"]


def test_active_staged_file_is_visible_to_other_readers():
    stream_state.set_source_connection_state("WII-F", "u", {"public"}, connected=True)
    assert stream_state.get_source_live_replay_path("WII-F") is None

    stream_state.set_source_active_staged_file("WII-F", "/app/ftp-staging/x/public/game.slp")
    assert str(stream_state.get_source_live_replay_path("WII-F")) == "/app/ftp-staging/x/public/game.slp"

    stream_state.set_source_active_staged_file("WII-F", None)
    assert stream_state.get_source_live_replay_path("WII-F") is None


def _age_connection(stream_state_db, upload_session_id, age):
    from datetime import datetime, timezone

    from app.models.stream_connection import StreamConnection

    old = datetime.now(timezone.utc) - age
    with stream_state_db() as db:
        row = db.query(StreamConnection).filter(StreamConnection.upload_session_id == upload_session_id).one()
        row.updated_at = old
        row.last_activity_at = old
        db.commit()


def test_disconnected_connections_are_pruned_after_retention_window(stream_state_db):
    from datetime import timedelta

    # One Wii login per game: each connect+disconnect leaves a row behind.
    stale_ids = []
    for _ in range(3):
        sid = stream_state.set_source_connection_state("WII-P", "u", {"public"}, connected=True)
        stream_state.set_source_connection_state("WII-P", "u", {"public"}, connected=False)
        stale_ids.append(sid)

    # Still recent -> kept so the UI can show the finished game.
    assert len(stream_state.get_stream_status_snapshot({"WII-P"})["sources"]) == 3

    for sid in stale_ids[:2]:
        _age_connection(stream_state_db, sid, stream_state.CONNECTION_RETENTION + timedelta(seconds=1))

    # Pruning runs when a new connection is registered.
    live_id = stream_state.set_source_connection_state("WII-Q", "u", {"public"}, connected=True)

    assert stream_state.get_connection(live_id) is not None
    assert stream_state.get_connection(stale_ids[2]) is not None
    assert stream_state.get_connection(stale_ids[0]) is None
    assert stream_state.get_connection(stale_ids[1]) is None


def test_connected_rows_are_never_pruned_even_if_idle(stream_state_db):
    live_id = stream_state.set_source_connection_state("WII-IDLE", "u", {"public"}, connected=True)
    _age_connection(stream_state_db, live_id, stream_state.CONNECTION_RETENTION * 4)

    stream_state.set_source_connection_state("WII-OTHER", "u", {"public"}, connected=True)
    snapshot = stream_state.get_stream_status_snapshot({"WII-IDLE"})

    assert [row["upload_session_id"] for row in snapshot["sources"]] == [live_id]
    # Snapshot rows are copies; mutating them must not leak back into shared state.
    snapshot["sources"][0]["stream_phase"] = "mutated"
    assert stream_state.get_latest_connection("WII-IDLE")["stream_phase"] == "started"
