"""add render job expiry

Revision ID: 0020_add_render_job_expiry
Revises: 0019_add_render_jobs
Create Date: 2026-08-20 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0020_add_render_job_expiry"
down_revision: Union[str, Sequence[str], None] = "0019_add_render_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("render_jobs", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("render_jobs", "expires_at")
