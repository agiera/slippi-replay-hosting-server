"""add replay browsing schema

Revision ID: 0003_add_replay_schema
Revises: 0002_create_refresh_tokens
Create Date: 2026-06-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_add_replay_schema"
down_revision: Union[str, Sequence[str], None] = "0002_create_refresh_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "file",
        sa.Column("_id", sa.Integer(), nullable=False),
        sa.Column("folder", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("birth_time", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("_id"),
        sa.UniqueConstraint("folder", "name", name="unique_folder_name_constraint"),
    )

    op.create_table(
        "game",
        sa.Column("_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("is_ranked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_teams", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.String(), nullable=True),
        sa.Column("platform", sa.String(), nullable=True),
        sa.Column("console_nickname", sa.String(), nullable=True),
        sa.Column("mode", sa.Integer(), nullable=True),
        sa.Column("last_frame", sa.Integer(), nullable=True),
        sa.Column("timer_type", sa.Integer(), nullable=True),
        sa.Column("starting_timer_secs", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("game_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("tiebreak_number", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["file_id"], ["file._id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("_id"),
        sa.UniqueConstraint("file_id"),
    )

    op.create_table(
        "player",
        sa.Column("_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("type", sa.Integer(), nullable=True),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("character_color", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("is_winner", sa.Integer(), nullable=True),
        sa.Column("start_stocks", sa.Integer(), nullable=True),
        sa.Column("connect_code", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("tag", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["game._id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("_id"),
        sa.UniqueConstraint("game_id", "port", name="unique_game_id_port_constraint"),
    )

    op.create_index("game_session_id_game_number_index", "game", ["session_id", "game_number"], unique=False)
    op.create_index("game_start_time_index", "game", ["start_time"], unique=False)
    op.create_index("player_user_id_index", "player", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("player_user_id_index", table_name="player")
    op.drop_index("game_start_time_index", table_name="game")
    op.drop_index("game_session_id_game_number_index", table_name="game")

    op.drop_table("player")
    op.drop_table("game")
    op.drop_table("file")
