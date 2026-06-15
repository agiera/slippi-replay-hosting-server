import hashlib

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.api_token import ApiToken
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    subject = payload.get("sub")
    if not subject or not subject.isdigit():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    user = db.get(User, int(subject))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_superuser(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "superuser":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required")
    return current_user


def get_active_api_token(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
) -> ApiToken:
    token_value = x_api_token
    if not token_value and authorization and authorization.lower().startswith("bearer "):
        token_value = authorization[7:].strip()

    if not token_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API token")

    token_hash = hashlib.sha256(token_value.encode("utf-8")).hexdigest()
    token_row = db.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash))
    if not token_row or token_row.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token")

    return token_row


def get_api_token_user(
    token_row: ApiToken = Depends(get_active_api_token),
    db: Session = Depends(get_db),
) -> User:

    user = db.get(User, token_row.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API token user not found")

    if user.role not in {"uploader", "superuser"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not approved to upload")

    return user