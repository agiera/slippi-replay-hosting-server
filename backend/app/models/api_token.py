from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.db.base import Base


class ApiToken(Base):
    __tablename__ = "api_tokens"
    __table_args__ = (UniqueConstraint("collection_name", name="uq_api_tokens_collection_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column("collection_name", String(64), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="api_tokens")
    repositories: Mapped[list["Repository"]] = relationship(
        secondary="api_token_repositories",
        back_populates="api_tokens",
    )
    tournaments: Mapped[list["TournamentSeries"]] = relationship(
        secondary="tournament_sources",
        back_populates="sources",
    )

    # Backward-compatible alias while APIs/UI transition from collection -> source.
    collection_name = synonym("source_name")
