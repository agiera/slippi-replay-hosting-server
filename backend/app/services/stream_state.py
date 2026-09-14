"""Live-stream state shared between the FTP ingest process and the API process.

All state lives in Postgres (``stream_connections`` / ``stream_events``) so the
API can be hot-reloaded or restarted without dropping in-flight games, and so the
FTP server can run in its own container. Writes are wrapped in row locks; a DB
trigger issues ``NOTIFY stream_state`` on commit so API listeners wake without
polling (see ``stream_notify``).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import SessionLocal
from app.models.stream_connection import StreamConnection
from app.models.stream_event import StreamEvent

# Sources whose most recent connection was updated within this window are
# included in snapshots; the frontend hides disconnected rows after 2 minutes.
SNAPSHOT_SOURCE_WINDOW = timedelta(hours=1)
# Recent completed events count as live activity for stream status.
SNAPSHOT_EVENT_WINDOW = timedelta(minutes=5)
EVENT_RETENTION = timedelta(hours=24)
CONNECTION_RETENTION = timedelta(hours=24)

_PREVIEW_FIELDS = (
    "port",
    "display_name",
    "tag",
    "slippi_code",
    "firmware",
    "character_id",
    "costume_id",
    "type",
    "is_cpu",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    # SQLite drops tzinfo on round-trip; Postgres preserves it.
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _factory(session_factory: sessionmaker | None) -> sessionmaker:
    return session_factory or SessionLocal


def normalize_ubjson_player_fields(player_meta: dict) -> dict:
    normalized: dict[str, str] = {}

    for key, value in player_meta.items():
        if not isinstance(value, str):
            continue
        key_norm = "".join(ch for ch in str(key).lower() if ch.isalnum())

        if key_norm in {"nametag", "tag"}:
            normalized["tag"] = value
        elif key_norm in {"name", "displayname", "display"}:
            normalized["display_name"] = value
        elif key_norm in {"slippi", "slippicode", "connectcode", "code"}:
            normalized["slippi_code"] = value
        elif key_norm in {"smashgg", "startgg"}:
            normalized["startgg_id"] = value
        elif key_norm == "parrygg":
            normalized["parrygg_id"] = value
        elif key_norm == "firmware":
            normalized["firmware"] = value

    return normalized


def _latest_connection_query(source_name: str):
    return (
        select(StreamConnection)
        .where(StreamConnection.source_name == source_name)
        .order_by(StreamConnection.connected_at.desc())
        .limit(1)
    )


def _latest_connected_row(db: Session, source_name: str, *, for_update: bool = False) -> StreamConnection | None:
    query = _latest_connection_query(source_name).where(StreamConnection.connected.is_(True))
    if for_update:
        query = query.with_for_update()
    return db.scalar(query)


def _enrichment_key_to_json(key: int | None) -> str:
    return "null" if key is None else str(key)


def _enrichment_key_from_json(key: str) -> int | None:
    if key == "null":
        return None
    try:
        return int(key)
    except (TypeError, ValueError):
        return None


def connection_to_dict(row: StreamConnection) -> dict:
    return {
        "source_name": row.source_name,
        "username": row.username,
        "upload_session_id": row.upload_session_id,
        "stream_game_id": row.stream_game_id,
        "repositories": list(row.repositories or []),
        "connected": bool(row.connected),
        "updated_at": _as_utc(row.updated_at),
        "player_preview": list(row.player_preview or []),
        "stage_preview": row.stage_preview,
        "pending_enrichment": {
            _enrichment_key_from_json(key): dict(value)
            for key, value in (row.pending_enrichment or {}).items()
        },
        "preview_seeded_from_enrichment": bool(row.preview_seeded_from_enrichment),
        "connected_at": _as_utc(row.connected_at),
        "last_activity_at": _as_utc(row.last_activity_at),
        "last_completed_at": _as_utc(row.last_completed_at),
        "stream_phase": row.stream_phase,
        "active_staged_path": row.active_staged_path,
        "active_upload_started_at": _as_utc(row.active_upload_started_at),
    }


def event_to_dict(row: StreamEvent) -> dict:
    return {
        "event_id": row.id,
        "source_name": row.source_name,
        "username": row.username,
        "upload_session_id": row.upload_session_id,
        "stream_game_id": row.stream_game_id,
        "repository": row.repository,
        "filename": row.filename,
        "status": row.status,
        "timestamp": _as_utc(row.created_at),
    }


# --------------------------------------------------------------------------- reads


def get_connection(upload_session_id: str, *, session_factory: sessionmaker | None = None) -> dict | None:
    with _factory(session_factory)() as db:
        row = db.get(StreamConnection, upload_session_id)
        return connection_to_dict(row) if row is not None else None


def get_latest_connection(source_name: str, *, session_factory: sessionmaker | None = None) -> dict | None:
    """Most recent *connected* session for a source, or None."""
    with _factory(session_factory)() as db:
        row = _latest_connected_row(db, source_name)
        return connection_to_dict(row) if row is not None else None


def get_source_live_replay_path(source_name: str, *, session_factory: sessionmaker | None = None) -> Path | None:
    state = get_latest_connection(source_name, session_factory=session_factory)
    value = state.get("active_staged_path") if state else None
    if not value:
        return None
    try:
        return Path(str(value))
    except Exception:
        return None


def session_started_without_completion(source_name: str, *, session_factory: sessionmaker | None = None) -> bool:
    state = get_latest_connection(source_name, session_factory=session_factory)
    if state is None:
        return False
    connected_at = state.get("connected_at")
    if connected_at is None:
        return False
    last_completed_at = state.get("last_completed_at")
    return last_completed_at is None or last_completed_at < connected_at


def get_stream_status_snapshot(
    source_names: set[str] | None = None,
    *,
    session_factory: sessionmaker | None = None,
) -> dict[str, list[dict]]:
    now = _now()
    with _factory(session_factory)() as db:
        source_query = select(StreamConnection).where(
            or_(
                StreamConnection.connected.is_(True),
                StreamConnection.updated_at >= now - SNAPSHOT_SOURCE_WINDOW,
            )
        )
        event_query = select(StreamEvent).where(StreamEvent.created_at >= now - SNAPSHOT_EVENT_WINDOW)
        if source_names is not None:
            source_query = source_query.where(StreamConnection.source_name.in_(source_names))
            event_query = event_query.where(StreamEvent.source_name.in_(source_names))

        sources = [connection_to_dict(row) for row in db.scalars(source_query.order_by(StreamConnection.connected_at.asc()))]
        events = [event_to_dict(row) for row in db.scalars(event_query.order_by(StreamEvent.id.desc()))]

    return {"sources": sources, "events": events}


def get_stream_events_since(
    last_event_id: int,
    source_names: set[str] | None = None,
    *,
    session_factory: sessionmaker | None = None,
) -> list[dict]:
    cutoff = _now() - SNAPSHOT_EVENT_WINDOW
    with _factory(session_factory)() as db:
        query = (
            select(StreamEvent)
            .where(StreamEvent.id > int(last_event_id), StreamEvent.created_at >= cutoff)
            .order_by(StreamEvent.id.asc())
        )
        if source_names is not None:
            query = query.where(StreamEvent.source_name.in_(source_names))
        return [event_to_dict(row) for row in db.scalars(query)]


# -------------------------------------------------------------------------- writes


def set_source_connection_state(
    source_name: str,
    username: str,
    repositories: set[str],
    connected: bool,
    *,
    session_factory: sessionmaker | None = None,
) -> str | None:
    """Open a new connection row (connected=True) or close the latest one.

    Returns the affected ``upload_session_id``.
    """
    now = _now()
    with _factory(session_factory)() as db:
        if connected:
            existing_last_completed_at = None
            for previous in db.scalars(
                select(StreamConnection)
                .where(StreamConnection.source_name == source_name, StreamConnection.connected.is_(True))
                .with_for_update()
            ):
                previous.connected = False
                previous.updated_at = now
                if existing_last_completed_at is None:
                    existing_last_completed_at = previous.last_completed_at

            upload_session_id = str(uuid.uuid4())
            # A new connection represents a new game upload; start the live preview
            # fresh so stale ports from a previous game do not linger and merge.
            db.add(
                StreamConnection(
                    upload_session_id=upload_session_id,
                    source_name=source_name,
                    username=username,
                    stream_game_id=str(uuid.uuid4()),
                    repositories=sorted(repositories),
                    connected=True,
                    connected_at=now,
                    updated_at=now,
                    last_activity_at=now,
                    last_completed_at=existing_last_completed_at,
                    stream_phase="started",
                    stage_preview=None,
                    player_preview=[],
                    pending_enrichment={},
                    preview_seeded_from_enrichment=False,
                    active_staged_path=None,
                    active_upload_started_at=None,
                )
            )
            _prune_connections(db, now)
            db.commit()
            return upload_session_id

        row = _latest_connected_row(db, source_name, for_update=True)
        if row is None:
            return None
        row.connected = False
        row.updated_at = now
        db.commit()
        return row.upload_session_id


def set_source_active_staged_file(
    source_name: str,
    staged_path: str | None,
    *,
    session_factory: sessionmaker | None = None,
) -> None:
    with _factory(session_factory)() as db:
        row = _latest_connected_row(db, source_name, for_update=True)
        if row is None:
            return
        row.active_staged_path = staged_path
        row.active_upload_started_at = _now() if staged_path else None
        db.commit()


def record_stream_event(
    source_name: str,
    username: str,
    repository: str,
    filename: str,
    status: str,
    *,
    session_factory: sessionmaker | None = None,
) -> dict:
    event_time = _now()
    with _factory(session_factory)() as db:
        row = _latest_connected_row(db, source_name, for_update=True)
        upload_session_id = row.upload_session_id if row is not None else None
        stream_game_id = row.stream_game_id if row is not None else None

        event = StreamEvent(
            source_name=source_name,
            username=username,
            upload_session_id=upload_session_id,
            stream_game_id=stream_game_id,
            repository=repository,
            filename=filename or "",
            status=status,
            created_at=event_time,
        )
        db.add(event)

        if row is not None:
            row.updated_at = event_time
            row.last_activity_at = event_time
            row.stream_phase = status
            if status in {"completed", "ended"}:
                row.last_completed_at = event_time

        db.execute(delete(StreamEvent).where(StreamEvent.created_at < event_time - EVENT_RETENTION))
        db.commit()

        print(
            "[FTP][EVENT] "
            f"source='{source_name}' "
            f"upload_session_id='{upload_session_id}' "
            f"stream_game_id='{stream_game_id}' "
            f"status='{status}' "
            f"repository='{repository}' "
            f"filename='{filename}'",
            flush=True,
        )
        return event_to_dict(event)


def set_source_player_preview(
    source_name: str,
    players: list[dict],
    *,
    stage: int | None = None,
    enrich_only: bool = False,
    session_factory: sessionmaker | None = None,
) -> None:
    """Update the live player preview for a source.

    The SLP metadata defines the roster of players that show up. When
    ``enrich_only`` is True (e.g. for the controller-metadata sidecar), incoming
    players may only fill in fields for ports that already exist in the roster;
    ports that are not already present are omitted rather than added.
    """

    def _port_sort_key(player: dict) -> int:
        try:
            return int(player.get("port"))
        except (TypeError, ValueError):
            return 99

    def _key_for(player: dict) -> int | None:
        try:
            return int(player.get("port")) if player.get("port") is not None else None
        except (TypeError, ValueError):
            return None

    def _normalize_preview_player(player: dict) -> dict | None:
        if not isinstance(player, dict):
            return None

        normalized_fields = normalize_ubjson_player_fields(player)

        port_value = player.get("port")
        try:
            port = int(port_value) if port_value is not None else None
        except (TypeError, ValueError):
            port = None

        # Callers pass already-normalized 1..4 ports; reject anything out of range.
        if port is not None and (port < 1 or port > 4):
            port = None

        display_name = normalized_fields.get("display_name") or player.get("display_name")
        tag = normalized_fields.get("tag") or player.get("tag") or player.get("nametag")
        slippi_code = (
            normalized_fields.get("slippi_code")
            or player.get("slippi_code")
            or player.get("connect_code")
            or player.get("connectCode")
        )
        firmware = normalized_fields.get("firmware") or player.get("firmware")

        character_id = player.get("character_id")
        if character_id is None:
            character_id = player.get("character")
        costume_id = player.get("costume_id")
        if costume_id is None:
            costume_id = player.get("costume")
        player_type = player.get("type")
        is_cpu = player.get("is_cpu")
        if is_cpu is None and player_type is not None:
            is_cpu = player_type == 1

        if not any([display_name, tag, slippi_code, firmware, port is not None]):
            return None

        return {
            "port": port,
            "display_name": display_name,
            "tag": tag,
            "slippi_code": slippi_code,
            "firmware": firmware,
            "character_id": character_id,
            "costume_id": costume_id,
            "type": player_type,
            "is_cpu": is_cpu,
        }

    incoming_preview: list[dict] = []
    for player in players:
        normalized_player = _normalize_preview_player(player)
        if normalized_player is not None:
            incoming_preview.append(normalized_player)
    incoming_preview.sort(key=_port_sort_key)

    normalized_stage: int | None = None
    if stage is not None:
        try:
            normalized_stage = int(stage)
        except (TypeError, ValueError):
            normalized_stage = None

    with _factory(session_factory)() as db:
        conn = _latest_connected_row(db, source_name, for_update=True)
        if conn is None:
            return

        existing_by_port: dict[int | None, dict] = {}
        for player in conn.player_preview or []:
            existing_by_port[_key_for(player)] = dict(player)

        # Per-port sidecar enrichment that has arrived but may not yet have a
        # matching SLP-roster player. The sidecar is uploaded before the .slp, so
        # its fields are stashed here and applied (fill-only) once the roster lands.
        pending_enrichment: dict[int | None, dict] = {
            _enrichment_key_from_json(key): dict(value)
            for key, value in (conn.pending_enrichment or {}).items()
        }
        preview_seeded_from_enrichment = bool(conn.preview_seeded_from_enrichment)

        if enrich_only:
            # The sidecar may only populate ports that are (or will be) part of the
            # SLP roster; it never introduces new players. Stash its fields and fill
            # in any matching roster ports without clobbering SLP-derived values.
            for player in incoming_preview:
                key = _key_for(player)
                fields = {
                    field: player.get(field)
                    for field in _PREVIEW_FIELDS
                    if player.get(field) is not None and player.get(field) != ""
                }
                merged_fields = dict(pending_enrichment.get(key, {}))
                merged_fields.update(fields)
                pending_enrichment[key] = merged_fields

                target = existing_by_port.get(key)
                if target is not None:
                    for field, value in merged_fields.items():
                        if target.get(field) in (None, ""):
                            target[field] = value

            if existing_by_port:
                merged_preview = list(existing_by_port.values())
            else:
                merged_preview = []
                preview_seeded_from_enrichment = False
        else:
            merged_preview = []
            incoming_keys: set[int | None] = set()
            for player in incoming_preview:
                key = _key_for(player)
                incoming_keys.add(key)

                merged = dict(existing_by_port.get(key, {}))
                for field in _PREVIEW_FIELDS:
                    value = player.get(field)
                    if value is not None and value != "":
                        merged[field] = value
                merged_preview.append(merged)

            for key, player in existing_by_port.items():
                if key in incoming_keys or preview_seeded_from_enrichment:
                    continue
                merged_preview.append(player)

            # Apply any sidecar enrichment received earlier to the roster ports,
            # filling only fields the SLP metadata did not already provide.
            for player in merged_preview:
                for field, value in (pending_enrichment.get(_key_for(player)) or {}).items():
                    if player.get(field) in (None, ""):
                        player[field] = value

            preview_seeded_from_enrichment = False

        merged_preview.sort(key=_port_sort_key)

        now = _now()
        # Assign fresh containers so SQLAlchemy sees the JSON columns as changed.
        conn.pending_enrichment = {
            _enrichment_key_to_json(key): value for key, value in pending_enrichment.items()
        }
        conn.preview_seeded_from_enrichment = preview_seeded_from_enrichment
        conn.player_preview = merged_preview
        if normalized_stage is not None:
            conn.stage_preview = normalized_stage
        conn.updated_at = now
        conn.last_activity_at = now
        db.commit()


def _prune_connections(db: Session, now: datetime) -> None:
    db.execute(
        delete(StreamConnection).where(
            StreamConnection.connected.is_(False),
            StreamConnection.updated_at < now - CONNECTION_RETENTION,
        )
    )


def clear_all(*, session_factory: sessionmaker | None = None) -> None:
    """Test helper: wipe stream state."""
    with _factory(session_factory)() as db:
        db.execute(delete(StreamEvent))
        db.execute(delete(StreamConnection))
        db.commit()
