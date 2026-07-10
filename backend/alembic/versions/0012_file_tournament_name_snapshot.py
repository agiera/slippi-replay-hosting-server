"""add file tournament name snapshot

Revision ID: 0012_file_tourney_snapshot
Revises: 0011_player_external_ids
Create Date: 2026-06-15 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0012_file_tourney_snapshot"
down_revision: Union[str, Sequence[str], None] = "0011_player_external_ids"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("file", sa.Column("tournament_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("file", "tournament_name")
