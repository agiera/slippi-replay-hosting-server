import hashlib

import pytest
from pyftpdlib.authorizers import AuthenticationFailed

from app.models.api_token import ApiToken
from app.models.repository import Repository
from app.models.user import User
from app.services.ftp_server import _authenticate_ftp_credentials


def test_ftp_auth_accepts_username_and_collection_token(db_session, testing_session_local):
    repo = Repository(name="public", is_public=True)
    user = User(
        username="ftpuser",
        email="ftpuser@example.com",
        hashed_password="x",
        role="uploader",
        is_active=True,
    )
    user.repositories.append(repo)
    db_session.add_all([repo, user])
    db_session.flush()

    raw_token = "slp_collection_token"
    token = ApiToken(
        user_id=user.id,
        collection_name="wii",
        token_prefix=raw_token[:12],
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
    )
    token.repositories.append(repo)
    db_session.add(token)
    db_session.commit()

    ctx = _authenticate_ftp_credentials("ftpuser", raw_token, session_factory=testing_session_local)
    assert ctx.user_id == user.id
    assert ctx.token_id == token.id
    assert ctx.repositories == {"public"}


def test_ftp_auth_rejects_wrong_token_or_role(db_session, testing_session_local):
    repo = Repository(name="public", is_public=True)
    user = User(
        username="notuploader",
        email="notuploader@example.com",
        hashed_password="x",
        role="user",
        is_active=True,
    )
    user.repositories.append(repo)
    db_session.add_all([repo, user])
    db_session.flush()

    raw_token = "slp_bad_role"
    token = ApiToken(
        user_id=user.id,
        collection_name="wii",
        token_prefix=raw_token[:12],
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
    )
    token.repositories.append(repo)
    db_session.add(token)
    db_session.commit()

    with pytest.raises(AuthenticationFailed):
        _authenticate_ftp_credentials("notuploader", raw_token, session_factory=testing_session_local)

    user.role = "uploader"
    db_session.add(user)
    db_session.commit()

    with pytest.raises(AuthenticationFailed):
        _authenticate_ftp_credentials("notuploader", "wrong-token", session_factory=testing_session_local)
