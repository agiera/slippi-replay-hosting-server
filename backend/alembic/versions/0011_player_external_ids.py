"""add player external ids

Revision ID: 0011_player_external_ids
Revises: 0010_tournament_repo_link
Create Date: 2026-06-15 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0011_player_external_ids"
down_revision: Union[str, Sequence[str], None] = "0010_tournament_repo_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("player", sa.Column("startgg_id", sa.String(), nullable=True))
    op.add_column("player", sa.Column("parrygg_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("player", "parrygg_id")
    op.drop_column("player", "startgg_id")
