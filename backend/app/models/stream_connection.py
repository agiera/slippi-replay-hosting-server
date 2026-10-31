from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StreamConnection(Base):
    """One FTP login from a source (Wii). Shared between the FTP and API processes."""

    __tablename__ = "stream_connections"

    upload_session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(150), nullable=False)
    stream_game_id: Mapped[str] = mapped_column(String(36), nullable=False)
    repositories: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stream_phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stage_preview: Mapped[int | None] = mapped_column(Integer, nullable=True)
    player_preview: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Keyed by port as a string ("1".."4" or "null") because JSON object keys must be strings.
    pending_enrichment: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    preview_seeded_from_enrichment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active_staged_path: Mapped[str | None] = mapped_column(String, nullable=True)
    active_upload_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
