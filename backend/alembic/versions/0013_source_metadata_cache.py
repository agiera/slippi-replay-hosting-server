"""add source metadata cache

Revision ID: 0013_source_metadata_cache
Revises: 0012_file_tourney_snapshot
Create Date: 2026-06-16 00:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_source_metadata_cache"
down_revision: Union[str, Sequence[str], None] = "0012_file_tourney_snapshot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_metadata",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("metadata_override", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_source_metadata_source_name", "source_metadata", ["source_name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_source_metadata_source_name", table_name="source_metadata")
    op.drop_table("source_metadata")
