"""stream state tables shared by the FTP and API processes

Revision ID: 0023_stream_state_tables
Revises: 0022_drop_render_jobs
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0023_stream_state_tables"
down_revision: Union[str, Sequence[str], None] = "0022_drop_render_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOTIFY_CHANNEL = "stream_state"


def upgrade() -> None:
    op.create_table(
        "stream_connections",
        sa.Column("upload_session_id", sa.String(length=36), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("stream_game_id", sa.String(length=36), nullable=False),
        sa.Column("repositories", sa.JSON(), nullable=False),
        sa.Column("connected", sa.Boolean(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stream_phase", sa.String(length=32), nullable=True),
        sa.Column("stage_preview", sa.Integer(), nullable=True),
        sa.Column("player_preview", sa.JSON(), nullable=False),
        sa.Column("pending_enrichment", sa.JSON(), nullable=False),
        sa.Column("preview_seeded_from_enrichment", sa.Boolean(), nullable=False),
        sa.Column("active_staged_path", sa.String(), nullable=True),
        sa.Column("active_upload_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("upload_session_id"),
    )
    op.create_index("ix_stream_connections_source_name", "stream_connections", ["source_name"])
    op.create_index("ix_stream_connections_connected", "stream_connections", ["connected"])
    op.create_index("ix_stream_connections_updated_at", "stream_connections", ["updated_at"])

    op.create_table(
        "stream_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("upload_session_id", sa.String(length=36), nullable=True),
        sa.Column("stream_game_id", sa.String(length=36), nullable=True),
        sa.Column("repository", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stream_events_source_name", "stream_events", ["source_name"])
    op.create_index("ix_stream_events_created_at", "stream_events", ["created_at"])

    if op.get_bind().dialect.name == "postgresql":
        # NOTIFY fires on commit, so API listeners only wake once the change is visible.
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION stream_state_notify() RETURNS trigger AS $$
            BEGIN
                PERFORM pg_notify('{NOTIFY_CHANNEL}', NEW.source_name);
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER stream_connections_notify
            AFTER INSERT OR UPDATE ON stream_connections
            FOR EACH ROW EXECUTE FUNCTION stream_state_notify();
            """
        )
        op.execute(
            """
            CREATE TRIGGER stream_events_notify
            AFTER INSERT ON stream_events
            FOR EACH ROW EXECUTE FUNCTION stream_state_notify();
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS stream_events_notify ON stream_events")
        op.execute("DROP TRIGGER IF EXISTS stream_connections_notify ON stream_connections")
        op.execute("DROP FUNCTION IF EXISTS stream_state_notify()")

    op.drop_index("ix_stream_events_created_at", table_name="stream_events")
    op.drop_index("ix_stream_events_source_name", table_name="stream_events")
    op.drop_table("stream_events")

    op.drop_index("ix_stream_connections_updated_at", table_name="stream_connections")
    op.drop_index("ix_stream_connections_connected", table_name="stream_connections")
    op.drop_index("ix_stream_connections_source_name", table_name="stream_connections")
    op.drop_table("stream_connections")
