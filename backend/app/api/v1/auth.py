from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, SignupRequest, TokenResponse
from app.schemas.user import UserPublic
from app.services.auth_service import authenticate_user, issue_token_pair, signup_user
from app.services.google_oidc import exchange_code_for_tokens, fetch_google_userinfo

router = APIRouter()


@router.post("/signup", response_model=TokenResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = signup_user(db, payload.username, payload.email, payload.password)
    access_token, refresh_token = issue_token_pair(db, user)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.username, payload.password)
    access_token, refresh_token = issue_token_pair(db, user)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token_payload = decode_token(payload.refresh_token)
    if not token_payload or token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    subject = token_payload.get("sub")
    token_id = token_payload.get("jti")
    if not subject or not subject.isdigit() or not token_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = db.get(User, int(subject))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    refresh_row = db.scalar(select(RefreshToken).where(RefreshToken.token_id == token_id))
    now_utc = datetime.now(timezone.utc)
    expires_at = refresh_row.expires_at if refresh_row else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if (
        not refresh_row
        or refresh_row.user_id != user.id
        or refresh_row.revoked_at is not None
        or (expires_at is not None and expires_at <= now_utc)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or expired")

    refresh_row.revoked_at = datetime.now(timezone.utc)
    db.add(refresh_row)
    db.commit()

    access_token, refresh_token = issue_token_pair(db, user)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post("/logout")
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    token_payload = decode_token(payload.refresh_token)
    if not token_payload or token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    token_id = token_payload.get("jti")
    if not token_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    refresh_row = db.scalar(select(RefreshToken).where(RefreshToken.token_id == token_id))
    if refresh_row and refresh_row.revoked_at is None:
        refresh_row.revoked_at = datetime.now(timezone.utc)
        db.add(refresh_row)
        db.commit()

    return {"message": "Logged out"}


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic.model_validate(current_user)


@router.get("/google/login")
def google_login() -> RedirectResponse:
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google OAuth is not configured")

    query = urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


@router.get("/google/callback")
async def google_callback(code: str = Query(...), db: Session = Depends(get_db)) -> RedirectResponse:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google OAuth is not configured")

    tokens = await exchange_code_for_tokens(
        code=code,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )
    userinfo = await fetch_google_userinfo(tokens["access_token"])

    google_sub = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name") or (email.split("@")[0] if email else None)

    if not google_sub or not email or not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Google profile")

    user = db.scalar(select(User).where((User.google_sub == google_sub) | (User.email == email)))
    if not user:
        user = User(username=name[:64], email=email, google_sub=google_sub)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.google_sub:
        user.google_sub = google_sub
        db.add(user)
        db.commit()
        db.refresh(user)

    access_token, refresh_token = issue_token_pair(db, user)
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/oauth-success?token={access_token}&refresh_token={refresh_token}"
    )
