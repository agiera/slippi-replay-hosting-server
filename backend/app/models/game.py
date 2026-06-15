from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Game(Base):
    __tablename__ = "game"
    __table_args__ = (
        Index("game_session_id_game_number_index", "session_id", "game_number"),
        Index("game_start_time_index", "start_time"),
    )

    _id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("file._id", ondelete="CASCADE"), nullable=False, unique=True)
    is_ranked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_teams: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_time: Mapped[str | None] = mapped_column(String, nullable=True)
    platform: Mapped[str | None] = mapped_column(String, nullable=True)
    console_nickname: Mapped[str | None] = mapped_column(String, nullable=True)
    mode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_frame: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timer_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starting_timer_secs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    game_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tiebreak_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    file: Mapped["File"] = relationship(back_populates="game")
    players: Mapped[list["Player"]] = relationship(back_populates="game", cascade="all, delete-orphan")