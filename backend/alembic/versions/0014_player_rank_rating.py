"""add player rank/rating columns

Revision ID: 0014_player_rank_rating
Revises: 0013_source_metadata_cache
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0014_player_rank_rating"
down_revision: Union[str, Sequence[str], None] = "0013_source_metadata_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("player", sa.Column("rank", sa.String(), nullable=True))
    op.add_column("player", sa.Column("rating", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("player", "rating")
    op.drop_column("player", "rank")
