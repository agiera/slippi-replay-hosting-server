"""add repository_id and sha256 to file for content-hash deduplication

Revision ID: 0024_file_content_hash
Revises: 0023_stream_state_tables
Create Date: 2026-10-30 00:00:00.000000

``repository_id`` is backfilled here from the ``uploads/<repo>/...`` folder
layout. ``sha256`` needs the original replay bytes, so it is backfilled
separately with ``python -m app.scripts.backfill_file_sha256``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0024_file_content_hash"
down_revision: Union[str, Sequence[str], None] = "0023_stream_state_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sanitize_segment(value: str, fallback: str) -> str:
    # Mirrors app.services.replay_upload._sanitize_segment at the time of writing.
    normalized = value.strip().replace("/", "-")
    return normalized or fallback


def upgrade() -> None:
    with op.batch_alter_table("file") as batch:
        batch.add_column(sa.Column("repository_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("sha256", sa.String(length=64), nullable=True))
        batch.create_foreign_key(
            "fk_file_repository_id_repositories", "repositories", ["repository_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_file_repository_id", ["repository_id"])
        batch.create_index("ix_file_sha256", ["sha256"])
        batch.create_unique_constraint("uq_file_repository_sha256", ["repository_id", "sha256"])

    bind = op.get_bind()
    repositories = bind.execute(sa.text("SELECT id, name FROM repositories")).all()
    for repo_id, repo_name in repositories:
        prefix = f"uploads/{_sanitize_segment(repo_name or '', 'public')}/"
        bind.execute(
            sa.text(
                "UPDATE file SET repository_id = :repo_id "
                "WHERE repository_id IS NULL AND substr(folder, 1, :prefix_len) = :prefix"
            ),
            {"repo_id": repo_id, "prefix": prefix, "prefix_len": len(prefix)},
        )


def downgrade() -> None:
    with op.batch_alter_table("file") as batch:
        batch.drop_constraint("uq_file_repository_sha256", type_="unique")
        batch.drop_index("ix_file_sha256")
        batch.drop_index("ix_file_repository_id")
        batch.drop_constraint("fk_file_repository_id_repositories", type_="foreignkey")
        batch.drop_column("sha256")
        batch.drop_column("repository_id")
