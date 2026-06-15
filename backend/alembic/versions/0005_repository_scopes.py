"""add repository scopes

Revision ID: 0005_repository_scopes
Revises: 0004_user_roles_tokens
Create Date: 2026-06-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_repository_scopes"
down_revision: Union[str, Sequence[str], None] = "0004_user_roles_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_repositories_name"),
    )
    op.create_index(op.f("ix_repositories_id"), "repositories", ["id"], unique=False)
    op.create_index(op.f("ix_repositories_name"), "repositories", ["name"], unique=True)

    op.create_table(
        "user_repositories",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "repository_id"),
    )

    op.create_table(
        "api_token_repositories",
        sa.Column("api_token_id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["api_token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("api_token_id", "repository_id"),
    )

    op.execute("INSERT INTO repositories (name, is_public) VALUES ('public', true)")

    op.execute(
        """
        INSERT INTO user_repositories (user_id, repository_id)
        SELECT u.id, r.id
        FROM users u
        CROSS JOIN repositories r
        WHERE r.is_public = true
        """
    )

    op.execute(
        """
        INSERT INTO api_token_repositories (api_token_id, repository_id)
        SELECT t.id, r.id
        FROM api_tokens t
        CROSS JOIN repositories r
        WHERE r.is_public = true
        """
    )


def downgrade() -> None:
    op.drop_table("api_token_repositories")
    op.drop_table("user_repositories")

    op.drop_index(op.f("ix_repositories_name"), table_name="repositories")
    op.drop_index(op.f("ix_repositories_id"), table_name="repositories")
    op.drop_table("repositories")
