"""add game_key, is_partial and source_size_bytes to file

Revision ID: 0025_file_game_key
Revises: 0024_file_content_hash
Create Date: 2026-10-30 00:00:00.000000

Values for existing rows are backfilled by ``python -m app.scripts.backfill_file_sha256``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0025_file_game_key"
down_revision: Union[str, Sequence[str], None] = "0024_file_content_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("file") as batch:
        batch.add_column(sa.Column("game_key", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("is_partial", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("source_size_bytes", sa.Integer(), nullable=True))
        batch.create_index("ix_file_repository_game_key", ["repository_id", "game_key"])


def downgrade() -> None:
    with op.batch_alter_table("file") as batch:
        batch.drop_index("ix_file_repository_game_key")
        batch.drop_column("source_size_bytes")
        batch.drop_column("is_partial")
        batch.drop_column("game_key")
