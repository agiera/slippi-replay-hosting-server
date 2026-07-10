import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.api_token import ApiToken
from app.models.file import File
from app.models.game import Game
from app.models.player import Player
from app.models.repository import Repository
from app.models.tournament_series import TournamentSeries
from app.services.peppi_ingest import parse_slippi_bytes
from app.services.tournament_slug import resolve_tournament_name
from app.services.view_cache import archive_view_replay_bytes, cache_view_replay_bytes, prune_view_cache


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
    content_hash = hashlib.sha256(data).hexdigest()[:8]

    suffix = fallback_suffix
    if parsed_replay is not None:
        suffix = ".peppi.json.gz"
    if not suffix:
        suffix = Path(original_name).suffix or ".slp"

    return f"{timestamp}_{p1}_vs_{p2}_{stage}_{content_hash}{suffix}"


def _normalize_player_overrides(player_overrides: list[dict] | None) -> dict[int, dict]:
    if not player_overrides:
        return {}

    by_port: dict[int, dict] = {}
    for player in player_overrides:
        try:
            port = int(player.get("port"))
        except (TypeError, ValueError):
            continue
        if port < 1 or port > 4:
            continue
        by_port[port] = player

    return by_port


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
    parse_replay=parse_slippi_bytes,
) -> File:
    if not original_name.lower().endswith((".slp", ".zlp")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .slp and .zlp files are supported")

    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

    token_repositories = list(token_row.repositories)
    token_repository_names = [repo.name for repo in token_repositories if repo.name]

    # Repository is always decided by token scope, not client-provided input.
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
    storage_bytes = data
    storage_name = original_name

    try:
        parsed_replay = parse_replay(data, suffix=Path(original_name).suffix)
        _apply_replay_metadata_overrides(parsed_replay, metadata_override)
        storage_bytes = parsed_replay.peppi_bytes
    except Exception:
        parsed_replay = None

    replay_start = _parse_start_time(parsed_replay.start_time) if parsed_replay else None
    folder_time = replay_start or now
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
    )
    db.add(row)
    db.flush()

    if parsed_replay is not None:
        game_row = Game(
            file_id=row._id,
            is_ranked=0,
            is_teams=parsed_replay.is_teams,
            stage=parsed_replay.stage,
            start_time=parsed_replay.start_time,
            last_frame=parsed_replay.last_frame,
        )
        db.add(game_row)
        db.flush()

        for player_data in parsed_replay.players:
            if player_data["port"] is None:
                continue
            db.add(
                Player(
                    game_id=game_row._id,
                    port=player_data["port"],
                    type=player_data["type"],
                    character_id=player_data["character_id"],
                    connect_code=player_data["connect_code"],
                    display_name=player_data["display_name"],
                    tag=player_data["tag"],
                    user_id=player_data["user_id"],
                    startgg_id=player_data.get("startgg_id"),
                    parrygg_id=player_data.get("parrygg_id"),
                    is_winner=player_data.get("is_winner"),
                )
            )

    return row
