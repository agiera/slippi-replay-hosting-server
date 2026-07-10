from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TournamentSeries(Base):
    __tablename__ = "tournament_series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, unique=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_tournament_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_tournament_name_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repository: Mapped["Repository"] = relationship()

    sources: Mapped[list["ApiToken"]] = relationship(
        secondary="tournament_sources",
        back_populates="tournaments",
    )

    @property
    def repository_name(self) -> str | None:
        return self.repository.name if self.repository else None

    @property
    def is_public(self) -> bool:
        return bool(self.repository and self.repository.is_public)
