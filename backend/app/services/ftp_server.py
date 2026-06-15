import hashlib
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from pyftpdlib.authorizers import AuthenticationFailed, DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.api_token import ApiToken
from app.models.user import User
from app.services.replay_upload import persist_replay_upload


@dataclass
class FTPSessionContext:
    user_id: int
    token_id: int
    repositories: set[str]


class CollectionTokenAuthorizer(DummyAuthorizer):
    def __init__(self) -> None:
        super().__init__()
        self._contexts: dict[int, FTPSessionContext] = {}
        self._lock = threading.Lock()

    def validate_authentication(self, username: str, password: str, handler) -> None:
        context = _authenticate_ftp_credentials(username=username, token_value=password)

        session_home = _prepare_session_home(username=username, repositories=context.repositories)

        with self._lock:
            if self.has_user(username):
                self.remove_user(username)
            # Store a non-secret placeholder password because credentials are validated above.
            self.add_user(username, "ftp-session", session_home, perm="elradfmwMT")
            self._contexts[id(handler)] = context

    def pop_context(self, handler) -> FTPSessionContext | None:
        with self._lock:
            return self._contexts.pop(id(handler), None)

    def clear_context(self, handler) -> None:
        with self._lock:
            self._contexts.pop(id(handler), None)


class ReplayFTPHandler(FTPHandler):
    ftp_session: FTPSessionContext | None = None

    def on_login(self, username: str) -> None:
        context = self.authorizer.pop_context(self)
        if context is None:
            raise AuthenticationFailed("Session context missing")
        self.ftp_session = context
        super().on_login(username)

    def on_file_received(self, file: str) -> None:
        staged_path = Path(file)
        try:
            if self.ftp_session is None:
                return

            original_name = staged_path.name
            data = staged_path.read_bytes()

            repository_name = self._resolve_repository_for_path(staged_path)
            with SessionLocal() as db:
                token_row = db.scalar(
                    select(ApiToken)
                    .options(selectinload(ApiToken.repositories))
                    .where(ApiToken.id == self.ftp_session.token_id)
                )
                if token_row is None or token_row.revoked_at is not None:
                    raise AuthenticationFailed("Collection token was revoked")

                persist_replay_upload(
                    db,
                    token_row=token_row,
                    repository_name=repository_name,
                    original_name=original_name,
                    data=data,
                )
                db.commit()

            print(f"[FTP] Uploaded {original_name} to repository '{repository_name}'", flush=True)
        except Exception as exc:
            print(f"[FTP] Failed to ingest uploaded file '{staged_path}': {exc}", flush=True)
        finally:
            try:
                staged_path.unlink(missing_ok=True)
            except Exception:
                pass

    def on_incomplete_file_received(self, file: str) -> None:
        try:
            Path(file).unlink(missing_ok=True)
        except Exception:
            pass

    def on_disconnect(self) -> None:
        self.authorizer.clear_context(self)
        super().on_disconnect()

    def _resolve_repository_for_path(self, staged_path: Path) -> str:
        if self.ftp_session is None:
            raise AuthenticationFailed("Session context missing")

        home_dir = Path(self.authorizer.get_home_dir(self.username)).resolve()
        rel_parts = staged_path.resolve().relative_to(home_dir).parts
        if rel_parts:
            candidate = rel_parts[0]
            if candidate in self.ftp_session.repositories:
                return candidate

        if len(self.ftp_session.repositories) == 1:
            return next(iter(self.ftp_session.repositories))

        if "public" in self.ftp_session.repositories:
            return "public"

        raise AuthenticationFailed(
            "Multiple repositories are authorized for this token. Upload into a repository directory."
        )


_server_lock = threading.Lock()
_server: FTPServer | None = None
_server_thread: threading.Thread | None = None


def _authenticate_ftp_credentials(
    username: str,
    token_value: str,
    session_factory=SessionLocal,
) -> FTPSessionContext:
    normalized_username = username.strip()
    if not normalized_username or not token_value:
        raise AuthenticationFailed("Missing username or collection token")

    token_hash = hashlib.sha256(token_value.encode("utf-8")).hexdigest()

    with session_factory() as db:
        user = db.scalar(
            select(User).where(
                User.username == normalized_username,
                User.is_active.is_(True),
            )
        )
        if user is None or user.role not in {"uploader", "superuser"}:
            raise AuthenticationFailed("Invalid account for FTP uploads")

        token_row = db.scalar(
            select(ApiToken)
            .options(selectinload(ApiToken.repositories))
            .where(
                ApiToken.user_id == user.id,
                ApiToken.token_hash == token_hash,
                ApiToken.revoked_at.is_(None),
            )
        )
        if token_row is None:
            raise AuthenticationFailed("Invalid collection token")

        repositories = {repo.name for repo in token_row.repositories}
        if not repositories:
            raise AuthenticationFailed("Collection token has no repository access")

        return FTPSessionContext(
            user_id=user.id,
            token_id=token_row.id,
            repositories=repositories,
        )


def _prepare_session_home(username: str, repositories: set[str]) -> str:
    base_dir = Path(settings.FTP_STAGING_DIR)
    session_dir = base_dir / username
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)
    session_dir.mkdir(parents=True, exist_ok=True)

    for repository_name in repositories:
        (session_dir / repository_name).mkdir(parents=True, exist_ok=True)

    return str(session_dir)


def _parse_passive_ports(raw: str) -> range | None:
    value = raw.strip()
    if not value:
        return None
    try:
        start_raw, end_raw = value.split("-", maxsplit=1)
        start = int(start_raw)
        end = int(end_raw)
    except Exception as exc:
        raise ValueError("FTP_PASSIVE_PORTS must use format 'start-end'") from exc

    if start <= 0 or end <= 0 or end < start:
        raise ValueError("FTP_PASSIVE_PORTS must be a positive ascending range")

    return range(start, end + 1)


def start_ftp_server() -> None:
    if not settings.FTP_ENABLED:
        return

    global _server, _server_thread

    with _server_lock:
        if _server is not None:
            return

        authorizer = CollectionTokenAuthorizer()
        handler_cls = ReplayFTPHandler
        handler_cls.authorizer = authorizer

        passive_ports = _parse_passive_ports(settings.FTP_PASSIVE_PORTS)
        if passive_ports is not None:
            handler_cls.passive_ports = passive_ports

        Path(settings.FTP_STAGING_DIR).mkdir(parents=True, exist_ok=True)

        _server = FTPServer((settings.FTP_HOST, settings.FTP_PORT), handler_cls)
        _server.max_cons = settings.FTP_MAX_CONNECTIONS
        _server.max_cons_per_ip = settings.FTP_MAX_CONNECTIONS_PER_IP

        _server_thread = threading.Thread(target=_server.serve_forever, kwargs={"timeout": 1.0}, daemon=True)
        _server_thread.start()

    print(f"[FTP] Server listening on {settings.FTP_HOST}:{settings.FTP_PORT}", flush=True)


def stop_ftp_server() -> None:
    global _server, _server_thread

    with _server_lock:
        if _server is None:
            return

        _server.close_all()
        if _server_thread is not None:
            _server_thread.join(timeout=2)

        _server = None
        _server_thread = None

    print("[FTP] Server stopped", flush=True)
