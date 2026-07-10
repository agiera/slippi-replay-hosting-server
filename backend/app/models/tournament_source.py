from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TournamentSource(Base):
    __tablename__ = "tournament_sources"
    __table_args__ = (UniqueConstraint("tournament_id", "token_id", name="uq_tournament_source_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tournament_id: Mapped[int] = mapped_column(
        ForeignKey("tournament_series.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_id: Mapped[int] = mapped_column(
        ForeignKey("api_tokens.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
