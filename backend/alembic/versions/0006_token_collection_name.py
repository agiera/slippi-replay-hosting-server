"""rename token name to collection_name and enforce uniqueness

Revision ID: 0006_token_collection_name
Revises: 0005_repository_scopes
Create Date: 2026-06-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_token_collection_name"
down_revision: Union[str, Sequence[str], None] = "0005_repository_scopes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("api_tokens", "name", new_column_name="collection_name")

    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY user_id, collection_name ORDER BY id) AS rn
            FROM api_tokens
        )
        UPDATE api_tokens t
        SET collection_name = t.collection_name || '-' || ranked.rn
        FROM ranked
        WHERE t.id = ranked.id
          AND ranked.rn > 1
        """
    )

    op.create_unique_constraint(
        "uq_api_tokens_user_collection_name",
        "api_tokens",
        ["user_id", "collection_name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_api_tokens_user_collection_name", "api_tokens", type_="unique")
    op.alter_column("api_tokens", "collection_name", new_column_name="name")
