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
    _normalize_metadata_override_payload,
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


def test_normalize_metadata_override_payload_infers_ports_from_player_list_order():
    payload = {
        "stage": "31",
        "players": [
            {"display_name": "Port 1 by position", "slippi_code": "P1#111"},
            {"display_name": "Port 2 by position", "slippi_code": "P2#222"},
        ],
    }

    normalized = _normalize_metadata_override_payload(payload)

    assert normalized["stage"] == 31
    assert normalized["players"][0]["port"] == 1
    assert normalized["players"][0]["display_name"] == "Port 1 by position"
    assert normalized["players"][1]["port"] == 2
    assert normalized["players"][1]["display_name"] == "Port 2 by position"


def test_normalize_metadata_override_payload_infers_ports_from_object_keys():
    payload = {
        "players": {
            "0": {"tag": "P1", "slippi_code": "ONE#001"},
            "2": {"tag": "P3", "slippi_code": "THREE#003"},
        }
    }

    normalized = _normalize_metadata_override_payload(payload)

    assert [player["port"] for player in normalized["players"]] == [1, 3]


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
                "port": 1,
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
                "port": 1,
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


def test_stream_preview_carries_slippi_character_and_cpu():
    source_name = "slp-preview-source"

    with _stream_state_lock:
        _source_connections.clear()

    _set_source_connection_state(source_name, "ftpuser", {"public"}, connected=True)
    # Seed a controller-only human (as the sidecar/on_login would).
    _set_source_player_preview(
        source_name,
        [{"port": 1, "display_name": "Human", "slippi_code": "HUM#001"}],
    )
    # Partial-SLP parse adds character/type/is_cpu for the human and the CPU on port 3,
    # so the live preview matches the completed row.
    _set_source_player_preview(
        source_name,
        [
            {"port": 1, "connect_code": "HUM#001", "character_id": 9, "type": 0, "is_cpu": False},
            {"port": 3, "character_id": 2, "type": 1, "is_cpu": True},
        ],
        stage=8,
    )

    with _stream_state_lock:
        state = dict(_source_connections[source_name])

    preview_by_port = {player["port"]: player for player in state["player_preview"]}
    assert state["stage_preview"] == 8
    assert set(preview_by_port) == {1, 3}
    assert preview_by_port[1]["display_name"] == "Human"
    assert preview_by_port[1]["character_id"] == 9
    assert preview_by_port[1]["is_cpu"] is False
    assert preview_by_port[3]["character_id"] == 2
    assert preview_by_port[3]["type"] == 1
    assert preview_by_port[3]["is_cpu"] is True


def test_stream_preview_enrich_only_omits_sidecar_only_players():
    source_name = "enrich-only-source"

    with _stream_state_lock:
        _source_connections.clear()

    _set_source_connection_state(source_name, "ftpuser", {"public"}, connected=True)
    # SLP metadata defines the roster: a human on port 1 and a CPU on port 3.
    _set_source_player_preview(
        source_name,
        [
            {"port": 1, "display_name": "Human", "character_id": 9, "type": 0, "is_cpu": False},
            {"port": 3, "character_id": 2, "type": 1, "is_cpu": True},
        ],
        stage=8,
    )
    # Sidecar enriches port 1 (firmware) and also carries a port-2 player that is
    # NOT in the SLP roster; enrich_only must drop the sidecar-only port.
    _set_source_player_preview(
        source_name,
        [
            {"port": 1, "firmware": "1.2.3"},
            {"port": 2, "display_name": "Sidecar Ghost", "firmware": "9.9.9"},
        ],
        enrich_only=True,
    )

    with _stream_state_lock:
        state = dict(_source_connections[source_name])

    preview_by_port = {player["port"]: player for player in state["player_preview"]}
    # Only the SLP-roster ports remain; the sidecar-only port 2 is omitted.
    assert set(preview_by_port) == {1, 3}
    # Port 1 keeps its SLP fields and gains the sidecar firmware.
    assert preview_by_port[1]["display_name"] == "Human"
    assert preview_by_port[1]["character_id"] == 9
    assert preview_by_port[1]["firmware"] == "1.2.3"
    # Port 3 is untouched by the sidecar.
    assert preview_by_port[3]["character_id"] == 2
    assert preview_by_port[3]["is_cpu"] is True


def test_stream_preview_sidecar_before_slp_roster_enriches_when_roster_lands():
    source_name = "sidecar-first-source"

    with _stream_state_lock:
        _source_connections.clear()

    _set_source_connection_state(source_name, "ftpuser", {"public"}, connected=True)
    # Real-world ordering: the sidecar (.meta.json) is uploaded before the .slp,
    # so its enrichment arrives while the roster is still empty.
    _set_source_player_preview(
        source_name,
        [
            {"port": 1, "firmware": "1.2.3"},
            {"port": 2, "display_name": "Sidecar Ghost", "firmware": "9.9.9"},
        ],
        enrich_only=True,
    )

    with _stream_state_lock:
        state = dict(_source_connections[source_name])
    preview_by_port = {player["port"]: player for player in state["player_preview"]}
    # Before the SLP roster lands, the sidecar seeds a temporary live preview so
    # the UI can update immediately.
    assert set(preview_by_port) == {1, 2}
    assert preview_by_port[1]["firmware"] == "1.2.3"
    assert preview_by_port[2]["display_name"] == "Sidecar Ghost"

    # The partial-SLP parse then lands the roster; the earlier sidecar firmware
    # must now fill in on the matching port without keeping the sidecar-only port.
    _set_source_player_preview(
        source_name,
        [
            {"port": 1, "display_name": "Human", "character_id": 9, "type": 0, "is_cpu": False},
            {"port": 3, "character_id": 2, "type": 1, "is_cpu": True},
        ],
        stage=8,
    )

    with _stream_state_lock:
        state = dict(_source_connections[source_name])

    preview_by_port = {player["port"]: player for player in state["player_preview"]}
    assert set(preview_by_port) == {1, 3}
    assert preview_by_port[1]["display_name"] == "Human"
    assert preview_by_port[1]["character_id"] == 9
    assert preview_by_port[1]["firmware"] == "1.2.3"
    assert preview_by_port[3]["character_id"] == 2


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
