from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class File(Base):
    __tablename__ = "file"
    __table_args__ = (
        UniqueConstraint("folder", "name", name="unique_folder_name_constraint"),
        # The same replay bytes may exist once per repository. Rows predating
        # content hashing have NULLs, which never conflict.
        UniqueConstraint("repository_id", "sha256", name="uq_file_repository_sha256"),
    )

    _id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folder: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    birth_time: Mapped[str | None] = mapped_column(String, nullable=True)
    tournament_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # SHA-256 (lowercase hex) of the replay bytes as uploaded, before any conversion.
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    game: Mapped["Game"] = relationship(back_populates="file", uselist=False, cascade="all, delete-orphan")
