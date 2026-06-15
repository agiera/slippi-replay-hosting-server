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
from app.services.peppi_ingest import parse_slippi_bytes


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


def persist_replay_upload(
    db: Session,
    *,
    token_row: ApiToken,
    repository_name: str,
    original_name: str,
    data: bytes,
    parse_replay=parse_slippi_bytes,
) -> File:
    if not original_name.lower().endswith((".slp", ".zlp")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .slp and .zlp files are supported")

    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

    normalized_repository = repository_name.strip() or "public"
    repository_row = db.scalar(select(Repository).where(Repository.name == normalized_repository))
    if not repository_row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository does not exist")

    token_repository_ids = {repo.id for repo in token_row.repositories}
    if repository_row.id not in token_repository_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API token is not authorized for the requested repository",
        )

    safe_repo_name = _sanitize_segment(repository_row.name, "public")
    safe_collection_name = _sanitize_segment(token_row.collection_name, "default")
    now = datetime.now(timezone.utc)
    folder_rel = f"uploads/{safe_repo_name}/{safe_collection_name}/{now.strftime('%Y/%m/%d')}"
    target_dir = Path(settings.REPLAY_STORAGE_DIR) / folder_rel
    target_dir.mkdir(parents=True, exist_ok=True)

    parsed_replay = None
    storage_bytes = data
    storage_name = original_name

    try:
        parsed_replay = parse_replay(data, suffix=Path(original_name).suffix)
        storage_bytes = parsed_replay.peppi_bytes
        storage_name = f"{Path(original_name).stem}.peppi.json.gz"
    except Exception:
        parsed_replay = None

    target_path = _resolve_unique_path(target_dir, storage_name)
    target_path.write_bytes(storage_bytes)

    row = File(
        folder=folder_rel,
        name=target_path.name,
        size_bytes=target_path.stat().st_size,
        birth_time=now.isoformat(),
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
                    is_winner=player_data.get("is_winner"),
                )
            )

    return row
