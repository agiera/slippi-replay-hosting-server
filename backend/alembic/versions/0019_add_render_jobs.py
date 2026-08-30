"""add render jobs

Revision ID: 0019_add_render_jobs
Revises: 0018_backfill_player_costume_id
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0019_add_render_jobs"
down_revision: Union[str, Sequence[str], None] = "0018_backfill_player_costume_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "render_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("worker_token_id", sa.Integer(), nullable=True),
        sa.Column("output_folder", sa.String(), nullable=True),
        sa.Column("output_name", sa.String(), nullable=True),
        sa.Column("output_size_bytes", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["file_id"], ["file._id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["worker_token_id"], ["api_tokens.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_render_jobs_id", "render_jobs", ["id"], unique=False)
    op.create_index("ix_render_jobs_file_id", "render_jobs", ["file_id"], unique=False)
    op.create_index("ix_render_jobs_status", "render_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_render_jobs_status", table_name="render_jobs")
    op.drop_index("ix_render_jobs_file_id", table_name="render_jobs")
    op.drop_index("ix_render_jobs_id", table_name="render_jobs")
    op.drop_table("render_jobs")
