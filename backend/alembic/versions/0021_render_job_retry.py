"""add render job retry tracking

Revision ID: 0021_render_job_retry
Revises: 0020_add_render_job_expiry
Create Date: 2026-08-23 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0021_render_job_retry"
down_revision: Union[str, Sequence[str], None] = "0020_add_render_job_expiry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "render_jobs",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "render_jobs",
        sa.Column("retry_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("render_jobs", "retry_at")
    op.drop_column("render_jobs", "attempts")
