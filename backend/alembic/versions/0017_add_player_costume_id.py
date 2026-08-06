"""add player costume id

Revision ID: 0017_add_player_costume_id
Revises: 0016_game_stream_identity
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0017_add_player_costume_id"
down_revision: Union[str, Sequence[str], None] = "0016_game_stream_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("player", sa.Column("costume_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("player", "costume_id")