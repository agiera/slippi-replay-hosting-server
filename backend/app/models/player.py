from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Player(Base):
    __tablename__ = "player"
    __table_args__ = (
        UniqueConstraint("game_id", "port", name="unique_game_id_port_constraint"),
        Index("player_user_id_index", "user_id"),
    )

    _id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("game._id", ondelete="CASCADE"), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    character_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    character_color: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_winner: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_stocks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    connect_code: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    tag: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    startgg_id: Mapped[str | None] = mapped_column(String, nullable=True)
    parrygg_id: Mapped[str | None] = mapped_column(String, nullable=True)

    game: Mapped["Game"] = relationship(back_populates="players")