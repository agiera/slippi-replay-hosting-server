import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.api_token import ApiToken
from app.models.repository import Repository
from app.models.user import User

PUBLIC_REPOSITORY_NAME = "public"


def get_or_create_public_repository(db: Session) -> Repository:
    repo = db.scalar(select(Repository).where(Repository.is_public.is_(True)))
    if repo:
        return repo

    by_name = db.scalar(select(Repository).where(Repository.name == PUBLIC_REPOSITORY_NAME))
    if by_name:
        if not by_name.is_public:
            by_name.is_public = True
            db.add(by_name)
            db.commit()
            db.refresh(by_name)
        return by_name

    repo = Repository(name=PUBLIC_REPOSITORY_NAME, is_public=True)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def ensure_user_in_public_repository(db: Session, user: User) -> None:
    public_repo = get_or_create_public_repository(db)
    if all(existing.id != public_repo.id for existing in user.repositories):
        user.repositories.append(public_repo)
        db.add(user)
        db.commit()
        db.refresh(user)


def _resolve_repositories_for_token(db: Session, user: User, repository_ids: list[int] | None) -> list[Repository]:
    available_ids = {repo.id for repo in user.repositories}
    if repository_ids is None or len(repository_ids) == 0:
        public_repo = get_or_create_public_repository(db)
        return [public_repo]

    unique_ids = list(dict.fromkeys(repository_ids))
    if len(unique_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A source can only belong to one repository",
        )

    selected = db.scalars(select(Repository).where(Repository.id.in_(unique_ids))).all()
    if len(selected) != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more repositories do not exist")

    unauthorized = [repo.id for repo in selected if repo.id not in available_ids]
    if unauthorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot assign API token to repositories outside your membership",
        )

    return selected


def ensure_superuser_exists(db: Session) -> None:
    public_repo = get_or_create_public_repository(db)

    if not settings.SUPERUSER_USERNAME or not settings.SUPERUSER_EMAIL or not settings.SUPERUSER_PASSWORD:
        return

    superuser = db.scalar(select(User).where(User.username == settings.SUPERUSER_USERNAME))
    if superuser:
        updates = False
        if superuser.role != "superuser":
            superuser.role = "superuser"
            updates = True
        if not superuser.hashed_password:
            superuser.hashed_password = get_password_hash(settings.SUPERUSER_PASSWORD)
            updates = True
        if updates:
            db.add(superuser)
            db.commit()
        ensure_user_in_public_repository(db, superuser)
        return

    existing_email = db.scalar(select(User).where(User.email == settings.SUPERUSER_EMAIL))
    if existing_email:
        existing_email.username = settings.SUPERUSER_USERNAME
        existing_email.role = "superuser"
        if not existing_email.hashed_password:
            existing_email.hashed_password = get_password_hash(settings.SUPERUSER_PASSWORD)
        db.add(existing_email)
        db.commit()
        ensure_user_in_public_repository(db, existing_email)
        return

    user = User(
        username=settings.SUPERUSER_USERNAME,
        email=settings.SUPERUSER_EMAIL,
        hashed_password=get_password_hash(settings.SUPERUSER_PASSWORD),
        role="superuser",
    )
    user.repositories.append(public_repo)
    db.add(user)
    db.commit()


def create_api_token_for_user(
    db: Session, user: User, source_name: str, repository_ids: list[int] | None = None
) -> tuple[ApiToken, str]:
    normalized_source_name = source_name.strip()
    if not normalized_source_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source name is required")

    existing = db.scalar(
        select(ApiToken).where(
            ApiToken.source_name == normalized_source_name,
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source name must be globally unique")

    repositories = _resolve_repositories_for_token(db, user, repository_ids)
    raw_token = f"slp_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    token = ApiToken(
        user_id=user.id,
        source_name=normalized_source_name,
        token_prefix=raw_token[:12],
        token_hash=token_hash,
        repositories=repositories,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token, raw_token


def revoke_api_token_for_user(db: Session, user: User, token_id: int) -> None:
    token = db.scalar(select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user.id))
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API token not found")
    if token.revoked_at is None:
        token.revoked_at = datetime.now(timezone.utc)
        db.add(token)
        db.commit()
