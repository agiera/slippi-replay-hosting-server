import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.api_token import ApiToken
from app.models.file import File
from app.models.game import Game
from app.models.player import Player
from app.models.repository import Repository
from app.models.tournament_series import TournamentSeries
from app.services.handwarmer import classify_handwarmer
from app.services.peppi_ingest import parse_slippi_bytes, parse_slippi_stage_partial
from app.services.slippi_profile import fetch_profile_by_connect_code
from app.services.tournament_slug import resolve_tournament_name
from app.services.replay_identity import identify_slp
from app.services.view_cache import (
    archive_view_replay_bytes,
    cache_view_replay_bytes,
    prune_view_cache,
    replay_artifact_paths,
)

logger = logging.getLogger(__name__)

_PENDING_DELETES_KEY = "replay_upload.pending_file_deletes"


def _delete_files_after_commit(db: Session, paths: list[Path]) -> None:
    """Remove files once the current transaction commits; a rollback keeps them."""
    db.info.setdefault(_PENDING_DELETES_KEY, []).extend(paths)


@event.listens_for(Session, "after_commit")
def _run_pending_file_deletes(session: Session) -> None:
    for path in session.info.pop(_PENDING_DELETES_KEY, []):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not remove replaced replay file '%s': %s", path, exc)


@event.listens_for(Session, "after_rollback")
def _discard_pending_file_deletes(session: Session) -> None:
    session.info.pop(_PENDING_DELETES_KEY, None)


def _unlink_quietly(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


class DuplicateReplayError(Exception):
    """Raised when identical replay bytes already exist in the target repository."""

    def __init__(self, existing: File):
        super().__init__(f"Replay already uploaded as {existing.folder}/{existing.name}")
        self.file_id = existing._id
        self.folder = existing.folder
        self.name = existing.name
        self.size_bytes = existing.size_bytes
        self.sha256 = existing.sha256


def compute_content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_file_by_hash(db: Session, *, repository_id: int, content_hash: str) -> File | None:
    return db.scalar(select(File).where(File.repository_id == repository_id, File.sha256 == content_hash))


def resolve_upload_repository(db: Session, token_row: ApiToken) -> Repository:
    """Return the repository an API token uploads into.

    The repository is always decided by token scope, never by client input.
    """
    token_repositories = list(token_row.repositories)
    token_repository_names = [repo.name for repo in token_repositories if repo.name]

    if len(token_repositories) == 1:
        normalized_repository = token_repositories[0].name
    else:
        tournament_repo_names = {
            tournament.repository.name
            for tournament in token_row.tournaments
            if tournament.repository and tournament.repository.name
        }
        if len(tournament_repo_names) == 1:
            normalized_repository = next(iter(tournament_repo_names))
        else:
            allowed_repositories = ", ".join(sorted(token_repository_names)) or "none"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Token must map to exactly one repository for uploads. "
                    f"Current token repositories: {allowed_repositories}"
                ),
            )

    repository_row = db.scalar(select(Repository).where(Repository.name == normalized_repository))
    if not repository_row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository does not exist")

    token_repository_ids = {repo.id for repo in token_repositories}
    if repository_row.id not in token_repository_ids:
        allowed_repositories = ", ".join(sorted(token_repository_names)) or "none"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API token is not authorized for the requested repository. Allowed repositories: {allowed_repositories}",
        )

    return repository_row


def _resolve_unique_path(base_dir: Path, filename: str) -> Path:
    candidate = base_dir / filename
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while candidate.exists():
        candidate = base_dir / f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate


def _sanitize_segment(value: str, fallback: str) -> str:
    normalized = value.strip().replace("/", "-")
    return normalized or fallback


def _parse_start_time(start_time: str | None) -> datetime | None:
    if not start_time:
        return None
    try:
        return datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_name_part(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or fallback


def _player_label(parsed_replay, player_index: int) -> str:
    if parsed_replay is None or player_index >= len(parsed_replay.players):
        return f"p{player_index + 1}"
    player_data = parsed_replay.players[player_index]
    return _safe_name_part(
        player_data.get("connect_code")
        or player_data.get("display_name")
        or player_data.get("tag"),
        f"p{player_index + 1}",
    )


def _build_storage_name(
    *,
    parsed_replay,
    fallback_suffix: str,
    original_name: str,
    data: bytes,
) -> str:
    replay_start = _parse_start_time(parsed_replay.start_time) if parsed_replay else None
    timestamp = (replay_start or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p1 = _player_label(parsed_replay, 0)
    p2 = _player_label(parsed_replay, 1)
    stage = f"s{parsed_replay.stage}" if parsed_replay and parsed_replay.stage is not None else "s-unknown"
    content_hash = compute_content_hash(data)[:8]

    suffix = fallback_suffix
    if parsed_replay is not None:
        suffix = ".peppi.json.gz"
    if not suffix:
        suffix = Path(original_name).suffix or ".slp"

    return f"{timestamp}_{p1}_vs_{p2}_{stage}_{content_hash}{suffix}"


def _coerce_port_from_field(raw_port: object) -> int | None:
    try:
        parsed = int(raw_port)
    except (TypeError, ValueError):
        return None

    if 1 <= parsed <= 4:
        return parsed
    if 0 <= parsed <= 3:
        return parsed + 1
    return None


def _coerce_port_from_hint(raw_port: object) -> int | None:
    try:
        parsed = int(raw_port)
    except (TypeError, ValueError):
        return None

    if 0 <= parsed <= 3:
        return parsed + 1
    if 1 <= parsed <= 4:
        return parsed
    return None


def _infer_override_port(player: dict, *, key_hint: object | None, list_index: int | None) -> int | None:
    for field in ("port", "player_port", "playerPort", "player_index", "playerIndex"):
        port = _coerce_port_from_field(player.get(field))
        if port is not None:
            return port

    if key_hint is not None:
        port = _coerce_port_from_hint(key_hint)
        if port is not None:
            return port

    if list_index is not None:
        return _coerce_port_from_hint(list_index)

    return None


def _normalize_player_overrides(player_overrides: list[dict] | dict | None) -> dict[int, dict]:
    if not player_overrides:
        return {}

    if isinstance(player_overrides, dict):
        entries = [(key, value, None) for key, value in player_overrides.items()]
    elif isinstance(player_overrides, list):
        entries = [(None, value, index) for index, value in enumerate(player_overrides)]
    else:
        return {}

    by_port: dict[int, dict] = {}
    for key_hint, player, list_index in entries:
        if not isinstance(player, dict):
            continue
        port = _infer_override_port(player, key_hint=key_hint, list_index=list_index)
        if port is None:
            continue
        by_port[port] = player

    return by_port


def _is_valid_port(port: object) -> bool:
    try:
        value = int(port)
    except (TypeError, ValueError):
        return False
    return 1 <= value <= 4


def _assign_missing_ports_from_overrides(parsed_replay, player_overrides: dict[int, dict]) -> None:
    if parsed_replay is None or not player_overrides:
        return

    used_ports: set[int] = set()
    missing_players: list[dict] = []

    for player in parsed_replay.players:
        port = player.get("port")
        if _is_valid_port(port) and int(port) not in used_ports:
            used_ports.add(int(port))
            continue
        missing_players.append(player)

    available_ports = [port for port in sorted(player_overrides.keys()) if port not in used_ports]
    for player, inferred_port in zip(missing_players, available_ports):
        player["port"] = inferred_port


def _players_from_metadata_override(metadata_override: dict | None) -> list[dict]:
    player_overrides = _normalize_player_overrides((metadata_override or {}).get("players"))
    players: list[dict] = []

    for port in sorted(player_overrides.keys()):
        override = player_overrides[port]
        character_id = None
        if override.get("character") is not None:
            try:
                character_id = int(override.get("character"))
            except (TypeError, ValueError):
                character_id = None

        players.append(
            {
                "port": port,
                "type": 0,
                "character_id": character_id,
                "costume_id": None,
                "connect_code": override.get("slippi_code"),
                "display_name": override.get("display_name"),
                "tag": override.get("tag"),
                "user_id": None,
                "startgg_id": override.get("startgg_id"),
                "parrygg_id": override.get("parrygg_id"),
                "is_winner": None,
            }
        )

    return players


def _apply_replay_metadata_overrides(parsed_replay, metadata_override: dict | None):
    if parsed_replay is None or not metadata_override:
        return

    stage_override = metadata_override.get("stage")
    if stage_override is not None and parsed_replay.stage is None:
        try:
            parsed_replay.stage = int(stage_override)
        except (TypeError, ValueError):
            pass

    player_overrides = _normalize_player_overrides(metadata_override.get("players"))
    if not player_overrides:
        return

    _assign_missing_ports_from_overrides(parsed_replay, player_overrides)

    for player in parsed_replay.players:
        port = player.get("port")
        if port is None:
            continue
        override = player_overrides.get(int(port))
        if not override:
            continue

        if override.get("display_name") is not None and not player.get("display_name"):
            player["display_name"] = override.get("display_name")
        if override.get("tag") is not None and not player.get("tag"):
            player["tag"] = override.get("tag")
        if override.get("slippi_code") is not None and not player.get("connect_code"):
            player["connect_code"] = override.get("slippi_code")
        if override.get("character") is not None and player.get("character_id") is None:
            try:
                player["character_id"] = int(override.get("character"))
            except (TypeError, ValueError):
                pass
        if override.get("costume") is not None and player.get("costume_id") is None:
            try:
                player["costume_id"] = int(override.get("costume"))
            except (TypeError, ValueError):
                pass

        startgg_id = override.get("startgg_id")
        parrygg_id = override.get("parrygg_id")
        existing_user_id = player.get("user_id")

        user_parts = []
        if startgg_id:
            user_parts.append(f"startgg:{startgg_id}")
        if parrygg_id:
            user_parts.append(f"parrygg:{parrygg_id}")
        if existing_user_id:
            user_parts.append(str(existing_user_id))
        if user_parts and not existing_user_id:
            player["user_id"] = "|".join(user_parts)

        if startgg_id and not player.get("startgg_id"):
            player["startgg_id"] = str(startgg_id)
        if parrygg_id and not player.get("parrygg_id"):
            player["parrygg_id"] = str(parrygg_id)


def persist_replay_upload(
    db: Session,
    *,
    token_row: ApiToken,
    repository_name: str,
    original_name: str,
    data: bytes,
    metadata_override: dict | None = None,
    stream_game_id: str | None = None,
    upload_started_at: datetime | None = None,
    parse_replay=parse_slippi_bytes,
) -> File:
    if not original_name.lower().endswith((".slp", ".zlp")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .slp and .zlp files are supported")

    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

    repository_row = resolve_upload_repository(db, token_row)

    content_hash = compute_content_hash(data)
    existing = find_file_by_hash(db, repository_id=repository_row.id, content_hash=content_hash)
    if existing is not None:
        raise DuplicateReplayError(existing)

    # Partial copies of a recording (live streams cut short) are replaced once a
    # more complete copy arrives; a copy no better than one we have is a duplicate.
    identity = identify_slp(data)
    superseded: list[File] = []
    if identity is not None:
        siblings = list(
            db.scalars(
                select(File).where(File.repository_id == repository_row.id, File.game_key == identity.game_key)
            )
        )
        partial_siblings = [row for row in siblings if row.is_partial]
        complete_siblings = [row for row in siblings if row.is_partial is False]
        if identity.is_partial:
            if complete_siblings:
                raise DuplicateReplayError(complete_siblings[0])
            longest = max(partial_siblings, key=lambda row: row.source_size_bytes or 0, default=None)
            if longest is not None and (longest.source_size_bytes or 0) >= len(data):
                raise DuplicateReplayError(longest)
        superseded = partial_siblings

    safe_repo_name = _sanitize_segment(repository_row.name, "public")
    safe_collection_name = _sanitize_segment(token_row.source_name, "default")
    now = datetime.now(timezone.utc)

    tournament_snapshot_name = None
    series_row = db.scalar(
        select(TournamentSeries).where(TournamentSeries.repository_id == repository_row.id)
    )
    if series_row is not None:
        resolved_name = series_row.current_tournament_name
        if series_row.provider and series_row.slug:
            fetched_name, fetched_at = resolve_tournament_name(
                series_row.provider,
                series_row.slug,
                cached_name=series_row.current_tournament_name,
                cached_at=series_row.current_tournament_name_fetched_at,
                force_refresh=False,
            )
            resolved_name = fetched_name or resolved_name
            if (
                fetched_name != series_row.current_tournament_name
                or fetched_at != series_row.current_tournament_name_fetched_at
            ):
                series_row.current_tournament_name = fetched_name
                series_row.current_tournament_name_fetched_at = fetched_at
                db.add(series_row)

        tournament_snapshot_name = resolved_name or series_row.name

    parsed_replay = None
    partial_stage: int | None = None
    storage_bytes = data
    storage_name = original_name

    try:
        parsed_replay = parse_replay(data, suffix=Path(original_name).suffix)
        _apply_replay_metadata_overrides(parsed_replay, metadata_override)
        storage_bytes = parsed_replay.peppi_bytes
    except Exception:
        parsed_replay = None
        try:
            partial_stage = parse_slippi_stage_partial(data, suffix=Path(original_name).suffix)
        except Exception:
            partial_stage = None

    replay_start = _parse_start_time(parsed_replay.start_time) if parsed_replay else None
    live_upload_start = upload_started_at if stream_game_id and upload_started_at is not None else None
    folder_time = live_upload_start or replay_start or now
    folder_rel = f"uploads/{safe_repo_name}/{safe_collection_name}/{folder_time.astimezone(timezone.utc).strftime('%Y/%m/%d')}"
    target_dir = Path(settings.REPLAY_STORAGE_DIR) / folder_rel
    target_dir.mkdir(parents=True, exist_ok=True)

    storage_name = _build_storage_name(
        parsed_replay=parsed_replay,
        fallback_suffix=Path(original_name).suffix,
        original_name=original_name,
        data=data,
    )

    target_path = _resolve_unique_path(target_dir, storage_name)
    target_path.write_bytes(storage_bytes)

    if parsed_replay is not None:
        cache_view_replay_bytes(folder_rel, target_path.name, Path(original_name).suffix, data)
        archive_view_replay_bytes(folder_rel, target_path.name, Path(original_name).suffix, data)
        prune_view_cache()

    row = File(
        folder=folder_rel,
        name=target_path.name,
        size_bytes=target_path.stat().st_size,
        birth_time=now.isoformat(),
        tournament_name=tournament_snapshot_name,
        repository_id=repository_row.id,
        sha256=content_hash,
        game_key=identity.game_key if identity else None,
        is_partial=identity.is_partial if identity else None,
        source_size_bytes=len(data),
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        # A concurrent upload of the same bytes won the race after our check.
        db.rollback()
        _unlink_quietly(replay_artifact_paths(folder_rel, target_path.name))
        existing = find_file_by_hash(db, repository_id=repository_row.id, content_hash=content_hash)
        if existing is None:
            raise
        raise DuplicateReplayError(existing) from None

    for old_row in superseded:
        logger.info(
            "Replacing partial replay %s/%s with more complete copy %s/%s",
            old_row.folder, old_row.name, row.folder, row.name,
        )
        _delete_files_after_commit(db, replay_artifact_paths(old_row.folder, old_row.name))
        db.delete(old_row)
    if superseded:
        db.flush()

    profile_cache: dict[str, object | None] = {}
    handwarmer = classify_handwarmer(parsed_replay)

    def _lookup_profile(connect_code: str | None):
        if not connect_code:
            return None
        if connect_code in profile_cache:
            return profile_cache[connect_code]
        profile = fetch_profile_by_connect_code(connect_code)
        profile_cache[connect_code] = profile
        return profile

    if parsed_replay is not None:
        game_start_time = parsed_replay.start_time
        if live_upload_start is not None:
            game_start_time = live_upload_start.astimezone(timezone.utc).isoformat()

        game_row = Game(
            file_id=row._id,
            is_ranked=0,
            is_teams=parsed_replay.is_teams,
            stage=parsed_replay.stage,
            start_time=game_start_time,
            last_frame=parsed_replay.last_frame,
            stream_game_id=stream_game_id,
            handwarmer_label=handwarmer.label,
            handwarmer_reason=handwarmer.reason,
            handwarmer_score=handwarmer.score,
            handwarmer_version=handwarmer.version,
        )
        db.add(game_row)
        db.flush()

        for player_data in parsed_replay.players:
            if player_data["port"] is None:
                continue
            profile = _lookup_profile(player_data.get("connect_code"))
            db.add(
                Player(
                    game_id=game_row._id,
                    port=player_data["port"],
                    type=player_data["type"],
                    character_id=player_data["character_id"],
                    costume_id=player_data.get("costume_id"),
                    team_id=player_data.get("team_id"),
                    connect_code=player_data["connect_code"],
                    display_name=player_data["display_name"],
                    tag=player_data["tag"],
                    user_id=player_data["user_id"],
                    startgg_id=player_data.get("startgg_id"),
                    parrygg_id=player_data.get("parrygg_id"),
                    is_winner=player_data.get("is_winner"),
                    rank=profile.rank if profile else None,
                    rating=profile.rating if profile else None,
                )
            )
    else:
        metadata_players = _players_from_metadata_override(metadata_override)
        if not metadata_players and partial_stage is None:
            return row

        # Persist stage/player fallback so rows can still render when full parse fails.
        game_start_time = live_upload_start.astimezone(timezone.utc).isoformat() if live_upload_start is not None else None
        game_row = Game(
            file_id=row._id,
            is_ranked=0,
            is_teams=0,
            stage=partial_stage,
            start_time=game_start_time,
            last_frame=None,
            stream_game_id=stream_game_id,
            handwarmer_label=handwarmer.label,
            handwarmer_reason=handwarmer.reason,
            handwarmer_score=handwarmer.score,
            handwarmer_version=handwarmer.version,
        )
        db.add(game_row)
        db.flush()

        for player_data in metadata_players:
            profile = _lookup_profile(player_data.get("connect_code"))
            db.add(
                Player(
                    game_id=game_row._id,
                    port=player_data["port"],
                    type=player_data["type"],
                    character_id=player_data["character_id"],
                    costume_id=player_data.get("costume_id"),
                    team_id=player_data.get("team_id"),
                    connect_code=player_data["connect_code"],
                    display_name=player_data["display_name"],
                    tag=player_data["tag"],
                    user_id=player_data["user_id"],
                    startgg_id=player_data.get("startgg_id"),
                    parrygg_id=player_data.get("parrygg_id"),
                    is_winner=player_data.get("is_winner"),
                    rank=profile.rank if profile else None,
                    rating=profile.rating if profile else None,
                )
            )

    return row
