"""enforce global token collection uniqueness

Revision ID: 0007_global_token_scope
Revises: 0006_token_collection_name
Create Date: 2026-06-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_global_token_scope"
down_revision: Union[str, Sequence[str], None] = "0006_token_collection_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   user_id,
                   ROW_NUMBER() OVER (PARTITION BY collection_name ORDER BY id) AS rn
            FROM api_tokens
        )
        UPDATE api_tokens t
        SET collection_name = t.collection_name || '-u' || ranked.user_id || '-' || ranked.rn
        FROM ranked
        WHERE t.id = ranked.id
          AND ranked.rn > 1
        """
    )

    op.drop_constraint("uq_api_tokens_user_collection_name", "api_tokens", type_="unique")
    op.create_unique_constraint("uq_api_tokens_collection_name", "api_tokens", ["collection_name"])


def downgrade() -> None:
    op.drop_constraint("uq_api_tokens_collection_name", "api_tokens", type_="unique")
    op.create_unique_constraint(
        "uq_api_tokens_user_collection_name",
        "api_tokens",
        ["user_id", "collection_name"],
    )
