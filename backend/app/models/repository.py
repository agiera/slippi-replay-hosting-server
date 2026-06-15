from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


user_repositories = Table(
    "user_repositories",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("repository_id", ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True),
)


api_token_repositories = Table(
    "api_token_repositories",
    Base.metadata,
    Column("api_token_id", ForeignKey("api_tokens.id", ondelete="CASCADE"), primary_key=True),
    Column("repository_id", ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True),
)


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("name", name="uq_repositories_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list["User"]] = relationship(
        secondary=user_repositories,
        back_populates="repositories",
    )
    api_tokens: Mapped[list["ApiToken"]] = relationship(
        secondary=api_token_repositories,
        back_populates="repositories",
    )
