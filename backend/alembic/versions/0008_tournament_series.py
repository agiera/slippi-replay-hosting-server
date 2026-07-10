"""add tournament series mapping

Revision ID: 0008_tournament_series
Revises: 0007_global_token_scope
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0008_tournament_series"
down_revision: Union[str, Sequence[str], None] = "0007_global_token_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tournament_series",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tournament_series_name"), "tournament_series", ["name"], unique=True)

    op.create_table(
        "tournament_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tournament_id", sa.Integer(), nullable=False),
        sa.Column("token_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournament_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tournament_id", "token_id", name="uq_tournament_source_pair"),
    )
    op.create_index(op.f("ix_tournament_sources_tournament_id"), "tournament_sources", ["tournament_id"], unique=False)
    op.create_index(op.f("ix_tournament_sources_token_id"), "tournament_sources", ["token_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tournament_sources_token_id"), table_name="tournament_sources")
    op.drop_index(op.f("ix_tournament_sources_tournament_id"), table_name="tournament_sources")
    op.drop_table("tournament_sources")

    op.drop_index(op.f("ix_tournament_series_name"), table_name="tournament_series")
    op.drop_table("tournament_series")
