"""link tournament series to repositories

Revision ID: 0010_tournament_repo_link
Revises: 0009_tournament_slug_meta
Create Date: 2026-06-15 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0010_tournament_repo_link"
down_revision: Union[str, Sequence[str], None] = "0009_tournament_slug_meta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tournament_series", sa.Column("repository_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tournament_series_repository_id",
        "tournament_series",
        "repositories",
        ["repository_id"],
        ["id"],
        ondelete="CASCADE",
    )

    conn = op.get_bind()
    tournament_rows = conn.execute(sa.text("SELECT id, name FROM tournament_series")).fetchall()

    for tournament_id, tournament_name in tournament_rows:
        repository_id = conn.execute(
            sa.text("SELECT id FROM repositories WHERE name = :name LIMIT 1"),
            {"name": tournament_name},
        ).scalar()

        if repository_id is None:
            repository_id = conn.execute(
                sa.text(
                    "INSERT INTO repositories (name, is_public) VALUES (:name, false) RETURNING id"
                ),
                {"name": tournament_name},
            ).scalar_one()

        conn.execute(
            sa.text("UPDATE tournament_series SET repository_id = :repo_id WHERE id = :id"),
            {"repo_id": repository_id, "id": tournament_id},
        )

    op.alter_column("tournament_series", "repository_id", nullable=False)
    op.create_unique_constraint("uq_tournament_series_repository_id", "tournament_series", ["repository_id"])


def downgrade() -> None:
    op.drop_constraint("uq_tournament_series_repository_id", "tournament_series", type_="unique")
    op.drop_constraint("fk_tournament_series_repository_id", "tournament_series", type_="foreignkey")
    op.drop_column("tournament_series", "repository_id")
