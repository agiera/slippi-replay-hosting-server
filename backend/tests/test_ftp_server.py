import hashlib

import pytest
from pyftpdlib.authorizers import AuthenticationFailed
from sqlalchemy import select

from app.models.api_token import ApiToken
from app.models.repository import Repository
from app.models.source_metadata import SourceMetadata
from app.models.user import User
from app.services.ftp_server import (
    _record_stream_event,
    _set_source_connection_state,
    _set_source_player_preview,
    _authenticate_ftp_credentials,
    _clear_source_metadata_override,
    _decode_site_slpmeta_ubjson,
    get_stream_events_since,
    _is_parsed_slippi_filename,
    _load_source_metadata_override,
    _source_connections,
    _stream_state_lock,
    _store_source_metadata_override,
)


def test_ftp_auth_accepts_username_and_collection_token(db_session, testing_session_local):
    repo = Repository(name="public", is_public=True)
    user = User(
        username="ftpuser",
        email="ftpuser@example.com",
        hashed_password="x",
        role="uploader",
        is_active=True,
    )
    user.repositories.append(repo)
    db_session.add_all([repo, user])
    db_session.flush()

    raw_token = "slp_collection_token"
    token = ApiToken(
        user_id=user.id,
        collection_name="wii",
        token_prefix=raw_token[:12],
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
    )
    token.repositories.append(repo)
    db_session.add(token)
    db_session.commit()

    ctx = _authenticate_ftp_credentials("ftpuser", raw_token, session_factory=testing_session_local)
    assert ctx.user_id == user.id
    assert ctx.token_id == token.id
    assert ctx.repositories == {"public"}


def test_ftp_auth_rejects_wrong_token_or_role(db_session, testing_session_local):
    repo = Repository(name="public", is_public=True)
    user = User(
        username="notuploader",
        email="notuploader@example.com",
        hashed_password="x",
        role="user",
        is_active=True,
    )
    user.repositories.append(repo)
    db_session.add_all([repo, user])
    db_session.flush()

    raw_token = "slp_bad_role"
    token = ApiToken(
        user_id=user.id,
        collection_name="wii",
        token_prefix=raw_token[:12],
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
    )
    token.repositories.append(repo)
    db_session.add(token)
    db_session.commit()

    with pytest.raises(AuthenticationFailed):
        _authenticate_ftp_credentials("notuploader", raw_token, session_factory=testing_session_local)

    user.role = "uploader"
    db_session.add(user)
    db_session.commit()

    with pytest.raises(AuthenticationFailed):
        _authenticate_ftp_credentials("notuploader", "wrong-token", session_factory=testing_session_local)


def _encode_len_prefixed_ascii(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes((ord("U"), len(raw))) + raw


def _encode_ubjson_object(payload: dict[str, object]) -> bytes:
    out = bytearray(b"{")
    for key, value in payload.items():
        out.extend(_encode_len_prefixed_ascii(key))
        if isinstance(value, dict):
            out.extend(_encode_ubjson_object(value))
        elif isinstance(value, str):
            out.append(ord("S"))
            out.extend(_encode_len_prefixed_ascii(value))
        else:
            raise AssertionError("test UBJSON helper only supports dict and str")
    out.append(ord("}"))
    return bytes(out)


def test_decode_site_slpmeta_ubjson_golden_payload():
    # Payload mirrors Wii controller metadata shape, keyed by controller port 0..3.
    ubj_payload = _encode_ubjson_object(
        {
            "0": {
                "nametag": "TAG0",
                "name": "Display Zero",
                "slippi": "ZERO#001",
                "smashgg": "startgg-user-0",
                "parrygg": "parry-user-0",
                "firmware": "1.2.3",
            },
            "2": {
                "nametag": "TAG2",
                "name": "Display Two",
                "slippi": "TWO#222",
                "smashgg": "startgg-user-2",
                "parrygg": "parry-user-2",
                "firmware": "9.9.9",
            },
        }
    )

    normalized = _decode_site_slpmeta_ubjson(ubj_payload)

    assert normalized == {
        "players": [
            {
                "port": 1,
                "tag": "TAG0",
                "display_name": "Display Zero",
                "slippi_code": "ZERO#001",
                "startgg_id": "startgg-user-0",
                "parrygg_id": "parry-user-0",
                "firmware": "1.2.3",
            },
            {
                "port": 3,
                "tag": "TAG2",
                "display_name": "Display Two",
                "slippi_code": "TWO#222",
                "startgg_id": "startgg-user-2",
                "parrygg_id": "parry-user-2",
                "firmware": "9.9.9",
            },
        ]
    }


def test_source_metadata_override_round_trip(db_session, testing_session_local):
    payload = {
        "players": [
            {
                "port": 1,
                "display_name": "Preview One",
                "tag": "P1",
                "slippi_code": "PREV#001",
                "firmware": "1.0.0",
            }
        ]
    }

    _store_source_metadata_override("test-source", payload, session_factory=testing_session_local)

    stored = db_session.scalar(select(SourceMetadata).where(SourceMetadata.source_name == "test-source"))
    assert stored is not None
    assert stored.metadata_override == payload
    assert _load_source_metadata_override("test-source", session_factory=testing_session_local) == payload

    _clear_source_metadata_override("test-source", session_factory=testing_session_local)
    assert db_session.scalar(select(SourceMetadata).where(SourceMetadata.source_name == "test-source")) is None


def test_stream_preview_merges_controller_and_slippi_metadata():
    source_name = "merge-source"

    with _stream_state_lock:
        _source_connections.clear()

    _set_source_connection_state(source_name, "ftpuser", {"public"}, connected=True)
    _set_source_player_preview(
        source_name,
        [
            {
                "port": 0,
                "display_name": "Controller Name",
                "tag": "CTRL",
                "firmware": "1.2.3",
            }
        ],
    )
    _set_source_player_preview(
        source_name,
        [
            {
                "port": 0,
                "slippi_code": "CTRL#001",
            }
        ],
        stage=31,
    )

    with _stream_state_lock:
        state = dict(_source_connections[source_name])

    assert state["stage_preview"] == 31
    assert len(state["player_preview"]) == 1
    merged = state["player_preview"][0]
    assert merged["port"] == 1
    assert merged["display_name"] == "Controller Name"
    assert merged["tag"] == "CTRL"
    assert merged["firmware"] == "1.2.3"
    assert merged["slippi_code"] == "CTRL#001"


def test_stream_phase_marks_ended_as_completion():
    source_name = "phase-source"

    with _stream_state_lock:
        _source_connections.clear()

    _set_source_connection_state(source_name, "ftpuser", {"public"}, connected=True)
    _record_stream_event(source_name, "ftpuser", "public", "", "started")
    _record_stream_event(source_name, "ftpuser", "public", "a.slp", "controller_metadata")
    _record_stream_event(source_name, "ftpuser", "public", "a.slp", "slippi_file_metadata")
    _record_stream_event(source_name, "ftpuser", "public", "a.slp", "ended")

    with _stream_state_lock:
        state = dict(_source_connections[source_name])

    assert state["stream_phase"] == "ended"
    assert state["last_completed_at"] is not None


def test_parsed_slippi_filename_helper():
    assert _is_parsed_slippi_filename("abc.peppi.json.gz") is True
    assert _is_parsed_slippi_filename("abc.slp") is False


def test_get_stream_events_since_returns_incremental_ordered_events():
    source_name = "events-source"

    with _stream_state_lock:
        _source_connections.clear()

    _set_source_connection_state(source_name, "ftpuser", {"public"}, connected=True)
    _record_stream_event(source_name, "ftpuser", "public", "", "started")
    _record_stream_event(source_name, "ftpuser", "public", "a.meta.json", "controller_metadata")
    _record_stream_event(source_name, "ftpuser", "public", "a.slp", "ended")

    all_events = get_stream_events_since(0, {source_name})
    assert len(all_events) >= 3
    assert [event["status"] for event in all_events[-3:]] == ["started", "controller_metadata", "ended"]

    first_cursor = int(all_events[-2]["event_id"])
    tail_events = get_stream_events_since(first_cursor, {source_name})
    assert len(tail_events) >= 1
    assert tail_events[-1]["status"] == "ended"
