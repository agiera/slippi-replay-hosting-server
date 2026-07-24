"""add stream identity fields to game

Revision ID: 0016_game_stream_identity
Revises: 0015_game_handwarmer_fields
Create Date: 2026-07-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0016_game_stream_identity"
down_revision: Union[str, Sequence[str], None] = "0015_game_handwarmer_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("game", sa.Column("stream_game_id", sa.String(length=64), nullable=True))
    op.create_index("game_stream_game_id_index", "game", ["stream_game_id"], unique=False)


def downgrade() -> None:
    op.drop_index("game_stream_game_id_index", table_name="game")
    op.drop_column("game", "stream_game_id")
