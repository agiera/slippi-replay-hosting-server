"""add tournament slug metadata

Revision ID: 0009_tournament_slug_meta
Revises: 0008_tournament_series
Create Date: 2026-06-15 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0009_tournament_slug_meta"
down_revision: Union[str, Sequence[str], None] = "0008_tournament_series"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tournament_series", sa.Column("provider", sa.String(length=32), nullable=True))
    op.add_column("tournament_series", sa.Column("slug", sa.String(length=255), nullable=True))
    op.add_column("tournament_series", sa.Column("current_tournament_name", sa.String(length=255), nullable=True))
    op.add_column(
        "tournament_series",
        sa.Column("current_tournament_name_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_tournament_series_provider"), "tournament_series", ["provider"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tournament_series_provider"), table_name="tournament_series")
    op.drop_column("tournament_series", "current_tournament_name_fetched_at")
    op.drop_column("tournament_series", "current_tournament_name")
    op.drop_column("tournament_series", "slug")
    op.drop_column("tournament_series", "provider")
