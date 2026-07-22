"""add game handwarmer classification fields

Revision ID: 0015_game_handwarmer_fields
Revises: 0014_player_rank_rating
Create Date: 2026-07-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0015_game_handwarmer_fields"
down_revision: Union[str, Sequence[str], None] = "0014_player_rank_rating"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("game", sa.Column("handwarmer_label", sa.String(), nullable=True))
    op.add_column("game", sa.Column("handwarmer_reason", sa.String(), nullable=True))
    op.add_column("game", sa.Column("handwarmer_score", sa.Float(), nullable=True))
    op.add_column("game", sa.Column("handwarmer_version", sa.Integer(), nullable=True))

    op.execute("UPDATE game SET handwarmer_label = 'unknown' WHERE handwarmer_label IS NULL")
    op.execute("UPDATE game SET handwarmer_version = 1 WHERE handwarmer_version IS NULL")

    op.alter_column("game", "handwarmer_label", existing_type=sa.String(), nullable=False)
    op.alter_column("game", "handwarmer_version", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    op.drop_column("game", "handwarmer_version")
    op.drop_column("game", "handwarmer_score")
    op.drop_column("game", "handwarmer_reason")
    op.drop_column("game", "handwarmer_label")
