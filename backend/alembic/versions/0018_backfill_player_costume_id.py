"""backfill player costume id from stored replay files

Revision ID: 0018_backfill_player_costume_id
Revises: 0017_add_player_costume_id
Create Date: 2026-08-05 00:10:00.000000

"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import MetaData, Table, select, update
import sqlalchemy as sa

from app.core.config import settings
from app.services.peppi_ingest import parse_slippi_bytes
from app.services.view_cache import get_cached_replay_path, rebuild_cached_replay_from_archive

# revision identifiers, used by Alembic.
revision: str = "0018_backfill_player_costume_id"
down_revision: Union[str, Sequence[str], None] = "0017_add_player_costume_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    metadata = MetaData()
    file_table = Table(
        "file",
        metadata,
        sa.Column("_id", sa.Integer),
        sa.Column("folder", sa.String),
        sa.Column("name", sa.String),
    )
    game_table = Table(
        "game",
        metadata,
        sa.Column("_id", sa.Integer),
        sa.Column("file_id", sa.Integer),
    )
    player_table = Table(
        "player",
        metadata,
        sa.Column("_id", sa.Integer),
        sa.Column("game_id", sa.Integer),
        sa.Column("port", sa.Integer),
        sa.Column("character_id", sa.Integer),
        sa.Column("character_color", sa.Integer),
        sa.Column("costume_id", sa.Integer),
    )

    rows = bind.execute(
        select(
            file_table.c._id.label("file_id"),
            file_table.c.folder,
            file_table.c.name,
            game_table.c._id.label("game_id"),
            player_table.c._id.label("player_id"),
            player_table.c.port,
            player_table.c.character_color,
            player_table.c.costume_id,
        )
        .select_from(file_table)
        .join(game_table, game_table.c.file_id == file_table.c._id)
        .join(player_table, player_table.c.game_id == game_table.c._id)
        .order_by(file_table.c._id.asc(), player_table.c.port.asc())
    ).all()

    replay_cache: dict[int, dict[int, int]] = {}
    storage_root = Path(settings.REPLAY_STORAGE_DIR)

    for row in rows:
        if row.file_id not in replay_cache:
            replay_cache[row.file_id] = _costumes_from_replay_file(storage_root / row.folder / row.name, row.folder, row.name)

        costumes_by_port = replay_cache[row.file_id]
        parsed_costume = costumes_by_port.get(int(row.port)) if row.port is not None else None

        if parsed_costume is not None and parsed_costume != row.costume_id:
            bind.execute(
                update(player_table)
                .where(player_table.c._id == row.player_id)
                .values(costume_id=parsed_costume)
            )

    # Safety net for rows whose replay could not be parsed from disk.
    bind.execute(
        update(player_table)
        .where(player_table.c.costume_id.is_(None))
        .where(player_table.c.character_color.is_not(None))
        .values(costume_id=player_table.c.character_color)
    )
    bind.execute(
        update(player_table)
        .where(player_table.c.costume_id.is_(None))
        .where(player_table.c.character_color.is_(None))
        .where(player_table.c.character_id.is_not(None))
        .values(costume_id=0)
    )


def downgrade() -> None:
    # This migration is data-only; keep values as-is on downgrade.
    pass


def _costumes_from_replay_file(path: Path, folder: str, name: str) -> dict[int, int]:
    if not path.exists() or not path.is_file():
        return {}

    raw_path = path
    if name.endswith(".peppi.json.gz"):
        raw_path = get_cached_replay_path(folder, name) or rebuild_cached_replay_from_archive(folder, name) or path

    if not raw_path.exists() or not raw_path.is_file():
        return {}

    try:
        parsed = parse_slippi_bytes(raw_path.read_bytes(), suffix=raw_path.suffix)
    except Exception:
        return {}

    costumes: dict[int, int] = {}
    for player in parsed.players:
        port = player.get("port")
        costume_id = player.get("costume_id")
        if port is None or costume_id is None:
            continue
        try:
            costumes[int(port)] = int(costume_id)
        except (TypeError, ValueError):
            continue
    return costumes
