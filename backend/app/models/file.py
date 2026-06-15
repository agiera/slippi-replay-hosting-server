from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class File(Base):
    __tablename__ = "file"
    __table_args__ = (UniqueConstraint("folder", "name", name="unique_folder_name_constraint"),)

    _id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folder: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    birth_time: Mapped[str | None] = mapped_column(String, nullable=True)

    game: Mapped["Game"] = relationship(back_populates="file", uselist=False, cascade="all, delete-orphan")