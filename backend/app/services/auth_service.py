from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, get_password_hash, verify_password
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.user_service import ensure_user_in_public_repository


def signup_user(db: Session, username: str, email: str, password: str) -> User:
    existing_user = db.scalar(select(User).where((User.username == username) | (User.email == email)))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    ensure_user_in_public_repository(db, user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if not user or not user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


def build_token_for_user(user: User) -> str:
    return create_access_token(str(user.id))


def issue_token_pair(db: Session, user: User) -> tuple[str, str]:
    access_token = create_access_token(str(user.id))
    token_id = uuid4().hex
    refresh_token = create_refresh_token(str(user.id), token_id)
    refresh_token_row = RefreshToken(
        token_id=token_id,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(refresh_token_row)
    db.commit()
    return access_token, refresh_token
