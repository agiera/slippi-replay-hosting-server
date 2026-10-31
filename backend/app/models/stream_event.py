from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StreamEvent(Base):
    """Append-only live-stream event log; ``id`` doubles as the SSE cursor."""

    __tablename__ = "stream_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(150), nullable=False)
    upload_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    stream_game_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    repository: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
