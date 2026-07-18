import hashlib
import binascii
import json
import os
import shutil
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pyftpdlib.authorizers import AuthenticationFailed, DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.api_token import ApiToken
from app.models.game import Game
from app.models.player import Player
from app.models.source_metadata import SourceMetadata
from app.models.user import User
from app.services.replay_upload import persist_replay_upload


@dataclass
class FTPSessionContext:
    user_id: int
    token_id: int
    username: str
    source_name: str
    repositories: set[str]
    repository_name: str


class SourceTokenAuthorizer(DummyAuthorizer):
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
    proto_cmds = FTPHandler.proto_cmds.copy()
    proto_cmds.update(
        {
            "SITE SLPMETA": {
                "perm": None,
                "auth": True,
                "arg": True,
                "help": "Syntax: SITE SLPMETA <SP> json-payload (set staged Slippi metadata override).",
            },
            "SITE SLPMETAUBJ": {
                "perm": None,
                "auth": True,
                "arg": True,
                "help": "Syntax: SITE SLPMETAUBJ <SP> hex-ubjson (set staged Slippi metadata override).",
            },
            "SITE SLPMETAUBJSON": {
                "perm": None,
                "auth": True,
                "arg": True,
                "help": "Syntax: SITE SLPMETAUBJSON <SP> hex-ubjson (set staged Slippi metadata override).",
            },
            "SITE CLEARSLPMETA": {
                "perm": None,
                "auth": True,
                "arg": None,
                "help": "Syntax: SITE CLEARSLPMETA (clear staged Slippi metadata override).",
            },
            "SITE SLPMETA_CLEAR": {
                "perm": None,
                "auth": True,
                "arg": None,
                "help": "Syntax: SITE SLPMETA_CLEAR (clear staged Slippi metadata override).",
            },
        }
    )

    ftp_session: FTPSessionContext | None = None
    metadata_override: dict | None = None
    _session_transfer_attempted: bool = False
    _session_replay_transfer_attempted: bool = False
    _pending_metadata_by_replay_name: dict[str, dict] = {}

    def pre_process_command(self, line: str, cmd: str, arg: str) -> None:
        try:
            print(f"[FTP][TRACE] CMD {cmd} arg='{arg or ''}'", flush=True)
        except Exception:
            pass
        super().pre_process_command(line, cmd, arg)

    def on_login(self, username: str) -> None:
        context = self.authorizer.pop_context(self)
        if context is None:
            raise AuthenticationFailed("Session context missing")
        self.ftp_session = context
        self.metadata_override = _load_source_metadata_override(context.source_name)
        self._session_transfer_attempted = False
        self._session_replay_transfer_attempted = False
        self._pending_metadata_by_replay_name = {}
        print(
            f"[FTP][TRACE] Login source='{context.source_name}' user='{context.username}' repos={sorted(context.repositories)}",
            flush=True,
        )
        _set_source_connection_state(context.source_name, context.username, context.repositories, connected=True)
        if self.metadata_override:
            _set_source_player_preview(
                context.source_name,
                self.metadata_override.get("players") or [],
                stage=self.metadata_override.get("stage"),
            )
        _record_stream_event(
            source_name=context.source_name,
            username=context.username,
            repository=context.repository_name,
            filename="",
            status="started",
        )
        super().on_login(username)

    def ftp_SITE(self, line: str) -> None:
        print(f"[FTP][TRACE] SITE raw='{line}'", flush=True)
        if not line:
            self.respond("501 SITE requires a command")
            return

        normalized_line = line.strip()
        # Some clients/handlers can pass "SITE ..." as the line payload.
        if normalized_line.upper().startswith("SITE "):
            normalized_line = normalized_line[5:].strip()
        if not normalized_line:
            self.respond("501 SITE requires a command")
            return

        command, _, rest = normalized_line.partition(" ")
        normalized_command = command.strip().upper()

        if normalized_command == "SLPMETA":
            self._handle_site_slpmeta(rest.strip())
            return

        if normalized_command in {"SLPMETAUBJ", "SLPMETAUBJSON"}:
            self._handle_site_slpmeta_ubjson(rest.strip())
            return

        if normalized_command in {"CLEARSLPMETA", "SLPMETA_CLEAR"}:
            self.metadata_override = None
            if self.ftp_session is not None:
                _clear_source_metadata_override(self.ftp_session.source_name)
            self.respond("200 Cleared staged Slippi metadata override")
            return

        super().ftp_SITE(line)

    # pyftpdlib may dispatch SITE subcommands directly via ftp_SITE_<SUBCMD>.
    def ftp_SITE_SLPMETA(self, line: str) -> None:
        print(f"[FTP][TRACE] SITE SLPMETA arg='{line}'", flush=True)
        self._handle_site_slpmeta(self._normalize_site_subcommand_arg(line, "SLPMETA"))

    def ftp_SITE_SLPMETAUBJ(self, line: str) -> None:
        print(f"[FTP][TRACE] SITE SLPMETAUBJ arg_len={len(line or '')}", flush=True)
        self._handle_site_slpmeta_ubjson(self._normalize_site_subcommand_arg(line, "SLPMETAUBJ"))

    def ftp_SITE_SLPMETAUBJSON(self, line: str) -> None:
        print(f"[FTP][TRACE] SITE SLPMETAUBJSON arg_len={len(line or '')}", flush=True)
        self._handle_site_slpmeta_ubjson(self._normalize_site_subcommand_arg(line, "SLPMETAUBJSON"))

    def ftp_TYPE(self, line: str) -> None:
        print(f"[FTP][TRACE] TYPE {line}", flush=True)
        super().ftp_TYPE(line)

    def ftp_PASV(self, line: str) -> None:
        print("[FTP][TRACE] PASV", flush=True)
        super().ftp_PASV(line)

    def ftp_STOR(self, file: str, mode: str = "w") -> None:
        self._session_transfer_attempted = True
        if not self._is_metadata_sidecar_filename(file):
            self._session_replay_transfer_attempted = True
        # Wii clients may upload to dynamic folders (e.g. /ngpr-17/...).
        # Ensure parent directories exist so STOR does not fail with 550.
        try:
            normalized_path = str(file or "").replace("\\", "/")

            # pyftpdlib passes local filesystem paths to ftp_STOR in many code paths.
            parent_local_dir = os.path.dirname(normalized_path)
            if parent_local_dir and normalized_path.startswith(settings.FTP_STAGING_DIR):
                os.makedirs(parent_local_dir, exist_ok=True)
            else:
                # Fallback when FTP-relative path is provided.
                fs_path = self.fs.ftp2fs(normalized_path)
                parent_dir = os.path.dirname(fs_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
        except Exception as exc:
            print(f"[FTP][TRACE] STOR mkdir failed for '{file}': {exc}", flush=True)
        print(f"[FTP][TRACE] STOR file='{file}' mode='{mode}'", flush=True)
        super().ftp_STOR(file, mode)

    def ftp_SITE_CLEARSLPMETA(self, _line: str) -> None:
        self.metadata_override = None
        if self.ftp_session is not None:
            _clear_source_metadata_override(self.ftp_session.source_name)
        self.respond("200 Cleared staged Slippi metadata override")

    def ftp_SITE_SLPMETA_CLEAR(self, _line: str) -> None:
        self.metadata_override = None
        if self.ftp_session is not None:
            _clear_source_metadata_override(self.ftp_session.source_name)
        self.respond("200 Cleared staged Slippi metadata override")

    def _handle_site_slpmeta(self, raw_json: str) -> None:
        if not raw_json:
            self.respond("501 Usage: SITE SLPMETA {\"stage\":31,\"players\":[...]}")
            return

        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            self.respond("501 Invalid JSON payload for SITE SLPMETA")
            return

        self._apply_metadata_override(payload)

    @staticmethod
    def _normalize_site_subcommand_arg(raw_line: str, subcommand: str) -> str:
        normalized = (raw_line or "").strip()
        upper = normalized.upper()
        subcommand_upper = subcommand.upper()

        if upper.startswith("SITE "):
            normalized = normalized[5:].strip()
            upper = normalized.upper()

        if upper == subcommand_upper:
            return ""

        prefix = f"{subcommand_upper} "
        if upper.startswith(prefix):
            return normalized[len(prefix):].strip()

        return normalized

    def _handle_site_slpmeta_ubjson(self, raw_hex: str) -> None:
        if not raw_hex:
            self.respond("501 Usage: SITE SLPMETAUBJ <hex-encoded-ubjson>")
            return

        try:
            ubjson_payload = binascii.unhexlify(raw_hex.encode("ascii"))
        except (ValueError, binascii.Error):
            self.respond("501 Invalid hex payload for SITE SLPMETAUBJ")
            return

        try:
            payload = _decode_site_slpmeta_ubjson(ubjson_payload)
        except ValueError as exc:
            self.respond(f"501 Invalid UBJSON payload for SITE SLPMETAUBJ: {exc}")
            return

        self._apply_metadata_override(payload)

    def _apply_metadata_override(self, payload: dict) -> None:

        if not isinstance(payload, dict):
            self.respond("501 SITE SLPMETA payload must be an object")
            return

        stage = payload.get("stage")
        if stage is not None:
            try:
                int(stage)
            except (TypeError, ValueError):
                self.respond("501 stage must be an integer")
                return

        players = payload.get("players")
        if players is not None and not isinstance(players, list):
            self.respond("501 players must be a JSON array")
            return

        if isinstance(players, list):
            for idx, player in enumerate(players):
                if not isinstance(player, dict):
                    self.respond(f"501 players[{idx}] must be an object")
                    return
                if "port" not in player:
                    self.respond(f"501 players[{idx}] requires 'port'")
                    return
                port_value = player.get("port")
                try:
                    port = int(port_value)
                except (TypeError, ValueError):
                    self.respond(f"501 players[{idx}].port must be an integer")
                    return
                if port < 1 or port > 4:
                    self.respond(f"501 players[{idx}].port must be between 1 and 4")
                    return

        self.metadata_override = payload
        if self.ftp_session is not None:
            _store_source_metadata_override(self.ftp_session.source_name, payload)
            players_payload = payload.get("players")
            if isinstance(players_payload, list) and players_payload:
                _set_source_player_preview(
                    self.ftp_session.source_name,
                    players_payload,
                    stage=payload.get("stage"),
                )
        self.respond("200 Applied Slippi metadata override for subsequent uploads")

    def on_file_received(self, file: str) -> None:
        staged_path = Path(file)
        repository_name = "unknown"
        self._session_transfer_attempted = True
        try:
            if self.ftp_session is None:
                return

            original_name = staged_path.name
            data = staged_path.read_bytes()

            if self._is_metadata_sidecar_filename(original_name):
                payload = _decode_uploaded_metadata_sidecar(data)
                replay_name = self._replay_name_from_metadata_sidecar(original_name)
                self._pending_metadata_by_replay_name[replay_name] = payload
                self.metadata_override = payload
                _store_source_metadata_override(self.ftp_session.source_name, payload)
                _set_source_player_preview(
                    self.ftp_session.source_name,
                    payload.get("players") or [],
                    stage=payload.get("stage"),
                )
                _record_stream_event(
                    source_name=self.ftp_session.source_name,
                    username=self.ftp_session.username,
                    repository=self.ftp_session.repository_name,
                    filename=original_name,
                    status="controller_metadata",
                )
                print(
                    f"[FTP] Applied metadata sidecar '{original_name}' for replay '{replay_name}'",
                    flush=True,
                )
                return

            replay_metadata_override = self._pending_metadata_by_replay_name.pop(original_name, None)
            if replay_metadata_override is not None:
                self.metadata_override = replay_metadata_override
                _set_source_player_preview(
                    self.ftp_session.source_name,
                    replay_metadata_override.get("players") or [],
                    stage=replay_metadata_override.get("stage"),
                )

            self._session_replay_transfer_attempted = True

            repository_name = self._resolve_repository_for_path(staged_path)
            with SessionLocal() as db:
                token_row = db.scalar(
                    select(ApiToken)
                    .options(selectinload(ApiToken.repositories))
                    .where(ApiToken.id == self.ftp_session.token_id)
                )
                if token_row is None or token_row.revoked_at is not None:
                    raise AuthenticationFailed("Source token was revoked")

                row = persist_replay_upload(
                    db,
                    token_row=token_row,
                    repository_name=repository_name,
                    original_name=original_name,
                    data=data,
                    metadata_override=replay_metadata_override or self.metadata_override,
                )
                if self.ftp_session is not None:
                    refreshed_override = _refresh_source_metadata_from_file(
                        db,
                        source_name=self.ftp_session.source_name,
                        file_id=row._id,
                    )
                    if refreshed_override:
                        self.metadata_override = refreshed_override
                        _set_source_player_preview(
                            self.ftp_session.source_name,
                            refreshed_override.get("players") or [],
                            stage=refreshed_override.get("stage"),
                        )
                db.commit()

            parsed_slippi = _is_parsed_slippi_filename(row.name)
            if parsed_slippi:
                _record_stream_event(
                    source_name=self.ftp_session.source_name,
                    username=self.ftp_session.username,
                    repository=repository_name,
                    filename=original_name,
                    status="slippi_file_metadata",
                )
                _record_stream_event(
                    source_name=self.ftp_session.source_name,
                    username=self.ftp_session.username,
                    repository=repository_name,
                    filename=original_name,
                    status="ended",
                )
            else:
                _record_stream_event(
                    source_name=self.ftp_session.source_name,
                    username=self.ftp_session.username,
                    repository=repository_name,
                    filename=original_name,
                    status="pending_parse",
                )

            print(f"[FTP] Uploaded {original_name} to repository '{repository_name}'", flush=True)
        except Exception as exc:
            if self.ftp_session is not None:
                _record_stream_event(
                    source_name=self.ftp_session.source_name,
                    username=self.ftp_session.username,
                    repository=repository_name,
                    filename=staged_path.name,
                    status="failed",
                )
            print(f"[FTP] Failed to ingest uploaded file '{staged_path}': {exc}", flush=True)
        finally:
            try:
                staged_path.unlink(missing_ok=True)
            except Exception:
                pass

    def on_incomplete_file_received(self, file: str) -> None:
        self._session_transfer_attempted = True
        if not self._is_metadata_sidecar_filename(Path(file).name):
            self._session_replay_transfer_attempted = True
        if self.ftp_session is not None:
            _record_stream_event(
                source_name=self.ftp_session.source_name,
                username=self.ftp_session.username,
                repository="unknown",
                filename=Path(file).name,
                status="incomplete",
            )
        try:
            Path(file).unlink(missing_ok=True)
        except Exception:
            pass

    def on_disconnect(self) -> None:
        if self.ftp_session is not None:
            print(
                f"[FTP][TRACE] Disconnect source='{self.ftp_session.source_name}' transfer_attempted={self._session_transfer_attempted}",
                flush=True,
            )
            if self._session_replay_transfer_attempted and _session_started_without_completion(self.ftp_session.source_name):
                _record_stream_event(
                    source_name=self.ftp_session.source_name,
                    username=self.ftp_session.username,
                    repository=self.ftp_session.repository_name,
                    filename="",
                    status="abandoned",
                )
                print(
                    f"[FTP][ERROR] Stream session for source '{self.ftp_session.source_name}' disconnected without any completed uploads",
                    flush=True,
                )
            _set_source_connection_state(
                self.ftp_session.source_name,
                self.ftp_session.username,
                self.ftp_session.repositories,
                connected=False,
            )
        self.authorizer.clear_context(self)
        super().on_disconnect()

    @staticmethod
    def _is_metadata_sidecar_filename(filename: str) -> bool:
        return str(filename).lower().endswith(".meta.json")

    @staticmethod
    def _replay_name_from_metadata_sidecar(filename: str) -> str:
        value = str(filename)
        if value.lower().endswith(".meta.json"):
            return value[:-10]
        return value

    def _resolve_repository_for_path(self, staged_path: Path) -> str:
        if self.ftp_session is None:
            raise AuthenticationFailed("Session context missing")

        # Repository selection is token-scoped and independent of uploaded path.
        return self.ftp_session.repository_name


def _decode_site_slpmeta_ubjson(data: bytes) -> dict:
    if not data:
        raise ValueError("empty payload")

    payload, pos = _parse_ubjson_object(data, 0)
    if pos != len(data):
        raise ValueError("unexpected trailing bytes")

    players: list[dict] = []
    for port_key, player_meta in payload.items():
        if not isinstance(player_meta, dict):
            continue
        try:
            parsed_port = int(str(port_key))
        except ValueError:
            continue

        # Wii metadata is keyed by 0..3, while replay overrides expect 1..4.
        port = parsed_port + 1 if 0 <= parsed_port <= 3 else parsed_port
        if port < 1 or port > 4:
            continue

        normalized_player = _normalize_ubjson_player_fields(player_meta)
        if not normalized_player:
            continue
        normalized_player["port"] = port
        players.append(normalized_player)

    players.sort(key=lambda player: int(player.get("port", 0)))
    return {"players": players}


def _decode_uploaded_metadata_sidecar(raw_data: bytes) -> dict:
    try:
        payload = json.loads(raw_data.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid metadata sidecar JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("metadata sidecar must be a JSON object")

    ubjson_hex = payload.get("ubjson_hex")
    if ubjson_hex is not None:
        if not isinstance(ubjson_hex, str):
            raise ValueError("ubjson_hex must be a string")
        try:
            ubjson_payload = binascii.unhexlify(ubjson_hex.encode("ascii"))
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid ubjson_hex value") from exc
        return _decode_site_slpmeta_ubjson(ubjson_payload)

    return payload


def _normalize_ubjson_player_fields(player_meta: dict) -> dict:
    normalized: dict[str, str] = {}

    for key, value in player_meta.items():
        if not isinstance(value, str):
            continue
        key_norm = "".join(ch for ch in str(key).lower() if ch.isalnum())

        if key_norm in {"nametag", "tag"}:
            normalized["tag"] = value
        elif key_norm in {"name", "displayname", "display"}:
            normalized["display_name"] = value
        elif key_norm in {"slippi", "slippicode", "connectcode", "code"}:
            normalized["slippi_code"] = value
        elif key_norm in {"smashgg", "startgg"}:
            normalized["startgg_id"] = value
        elif key_norm == "parrygg":
            normalized["parrygg_id"] = value
        elif key_norm == "firmware":
            normalized["firmware"] = value

    return normalized


def _parse_ubjson_object(data: bytes, start: int) -> tuple[dict, int]:
    if start >= len(data) or data[start] != ord("{"):
        raise ValueError("expected object opener")

    pos = start + 1
    out: dict[str, object] = {}

    while True:
        if pos >= len(data):
            raise ValueError("unterminated object")
        if data[pos] == ord("}"):
            return out, pos + 1

        key, pos = _parse_ubjson_len_prefixed_ascii(data, pos)
        value, pos = _parse_ubjson_value(data, pos)
        out[key] = value


def _parse_ubjson_value(data: bytes, start: int) -> tuple[object, int]:
    if start >= len(data):
        raise ValueError("missing value marker")

    marker = data[start]
    if marker == ord("{"):
        return _parse_ubjson_object(data, start)

    if marker == ord("S"):
        return _parse_ubjson_len_prefixed_ascii(data, start + 1)

    raise ValueError(f"unsupported value marker: {chr(marker)!r}")


def _parse_ubjson_len_prefixed_ascii(data: bytes, start: int) -> tuple[str, int]:
    length, pos = _parse_ubjson_length(data, start)
    end = pos + length
    if end > len(data):
        raise ValueError("truncated string")

    try:
        text = data[pos:end].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("non-ascii text") from exc

    return text, end


def _parse_ubjson_length(data: bytes, start: int) -> tuple[int, int]:
    if start + 2 > len(data):
        raise ValueError("truncated length marker")

    marker = data[start]
    raw = data[start + 1]
    if marker == ord("U"):
        length = raw
    elif marker == ord("i"):
        length = raw - 256 if raw > 127 else raw
    else:
        raise ValueError("unsupported length marker")

    if length < 0:
        raise ValueError("negative length")

    return length, start + 2


_server_lock = threading.Lock()
_server: FTPServer | None = None
_server_thread: threading.Thread | None = None

_stream_state_lock = threading.Lock()
_source_connections: dict[str, dict] = {}
_recent_events: deque[dict] = deque(maxlen=500)
_stream_event_sequence: int = 0


def _is_parsed_slippi_filename(filename: str | None) -> bool:
    return str(filename or "").lower().endswith(".peppi.json.gz")


def _set_source_connection_state(source_name: str, username: str, repositories: set[str], connected: bool) -> None:
    with _stream_state_lock:
        if connected:
            existing_preview = []
            existing_stage_preview = None
            existing_last_completed_at = None
            if source_name in _source_connections:
                existing_preview = list(_source_connections[source_name].get("player_preview") or [])
                existing_stage_preview = _source_connections[source_name].get("stage_preview")
                existing_last_completed_at = _source_connections[source_name].get("last_completed_at")
            now = datetime.now(timezone.utc)
            _source_connections[source_name] = {
                "source_name": source_name,
                "username": username,
                "repositories": sorted(repositories),
                "connected": True,
                "updated_at": now,
                "player_preview": existing_preview,
                "stage_preview": existing_stage_preview,
                "connected_at": now,
                "last_activity_at": now,
                "last_completed_at": existing_last_completed_at,
                "stream_phase": "started",
            }
        else:
            if source_name in _source_connections:
                _source_connections[source_name]["connected"] = False
                _source_connections[source_name]["updated_at"] = datetime.now(timezone.utc)


def _set_source_player_preview(source_name: str, players: list[dict], *, stage: int | None = None) -> None:
    def _port_sort_key(player: dict) -> int:
        try:
            return int(player.get("port"))
        except (TypeError, ValueError):
            return 99

    def _normalize_preview_player(player: dict) -> dict | None:
        if not isinstance(player, dict):
            return None

        normalized_fields = _normalize_ubjson_player_fields(player)

        port_value = player.get("port")
        try:
            port = int(port_value) if port_value is not None else None
        except (TypeError, ValueError):
            port = None

        # Accept either 1..4 or legacy 0..3 indexing.
        if port is not None and 0 <= port <= 3:
            port += 1
        if port is not None and (port < 1 or port > 4):
            port = None

        display_name = normalized_fields.get("display_name") or player.get("display_name")
        tag = normalized_fields.get("tag") or player.get("tag") or player.get("nametag")
        slippi_code = (
            normalized_fields.get("slippi_code")
            or player.get("slippi_code")
            or player.get("connect_code")
            or player.get("connectCode")
        )
        firmware = normalized_fields.get("firmware") or player.get("firmware")

        if not any([display_name, tag, slippi_code, firmware, port is not None]):
            return None

        return {
            "port": port,
            "display_name": display_name,
            "tag": tag,
            "slippi_code": slippi_code,
            "firmware": firmware,
        }

    incoming_preview: list[dict] = []
    for player in players:
        normalized_player = _normalize_preview_player(player)
        if normalized_player is None:
            continue
        incoming_preview.append(normalized_player)

    incoming_preview.sort(key=_port_sort_key)

    normalized_stage: int | None = None
    if stage is not None:
        try:
            normalized_stage = int(stage)
        except (TypeError, ValueError):
            normalized_stage = None

    with _stream_state_lock:
        if source_name not in _source_connections:
            return

        existing_preview = _source_connections[source_name].get("player_preview") or []
        existing_by_port: dict[int | None, dict] = {}
        for player in existing_preview:
            try:
                key = int(player.get("port")) if player.get("port") is not None else None
            except (TypeError, ValueError):
                key = None
            existing_by_port[key] = dict(player)

        merged_preview: list[dict] = []
        incoming_keys: set[int | None] = set()
        for player in incoming_preview:
            try:
                key = int(player.get("port")) if player.get("port") is not None else None
            except (TypeError, ValueError):
                key = None
            incoming_keys.add(key)

            merged = dict(existing_by_port.get(key, {}))
            for field in ("port", "display_name", "tag", "slippi_code", "firmware"):
                value = player.get(field)
                if value is not None and value != "":
                    merged[field] = value
            merged_preview.append(merged)

        for key, player in existing_by_port.items():
            if key in incoming_keys:
                continue
            merged_preview.append(player)

        merged_preview.sort(key=_port_sort_key)

        now = datetime.now(timezone.utc)
        _source_connections[source_name]["player_preview"] = merged_preview
        if normalized_stage is not None:
            _source_connections[source_name]["stage_preview"] = normalized_stage
        _source_connections[source_name]["updated_at"] = now
        _source_connections[source_name]["last_activity_at"] = now


def _load_source_metadata_override(source_name: str, session_factory=SessionLocal) -> dict | None:
    with session_factory() as db:
        row = db.scalar(select(SourceMetadata).where(SourceMetadata.source_name == source_name))
        if row is None or not isinstance(row.metadata_override, dict):
            return None
        return row.metadata_override


def _store_source_metadata_override(source_name: str, payload: dict, session_factory=SessionLocal) -> None:
    with session_factory() as db:
        row = db.scalar(select(SourceMetadata).where(SourceMetadata.source_name == source_name))
        if row is None:
            row = SourceMetadata(source_name=source_name, metadata_override=payload)
        else:
            row.metadata_override = payload
        db.add(row)
        db.commit()


def _clear_source_metadata_override(source_name: str, session_factory=SessionLocal) -> None:
    with session_factory() as db:
        row = db.scalar(select(SourceMetadata).where(SourceMetadata.source_name == source_name))
        if row is None:
            return
        db.delete(row)
        db.commit()


def _refresh_source_metadata_from_file(db, *, source_name: str, file_id: int) -> dict | None:
    source_row = db.scalar(select(SourceMetadata).where(SourceMetadata.source_name == source_name))
    existing_payload = source_row.metadata_override if source_row and isinstance(source_row.metadata_override, dict) else {}

    game_row = db.scalar(select(Game).where(Game.file_id == file_id))
    if game_row is None:
        return source_row.metadata_override if source_row else None

    existing_players_by_port: dict[int, dict] = {}
    existing_players = existing_payload.get("players") if isinstance(existing_payload, dict) else None
    if isinstance(existing_players, list):
        for player in existing_players:
            if not isinstance(player, dict):
                continue
            try:
                port = int(player.get("port"))
            except (TypeError, ValueError):
                continue
            existing_players_by_port[port] = dict(player)

    merged_payload: dict = dict(existing_payload) if isinstance(existing_payload, dict) else {}
    if game_row.stage is not None:
        merged_payload["stage"] = game_row.stage

    merged_players: list[dict] = []
    for player_row in db.scalars(select(Player).where(Player.game_id == game_row._id).order_by(Player.port)).all():
        merged_player = dict(existing_players_by_port.get(player_row.port, {}))
        merged_player["port"] = player_row.port
        if player_row.display_name:
            merged_player["display_name"] = player_row.display_name
        if player_row.tag:
            merged_player["tag"] = player_row.tag
        if player_row.connect_code:
            merged_player["slippi_code"] = player_row.connect_code
        if player_row.character_id is not None:
            merged_player["character"] = player_row.character_id
        if player_row.startgg_id:
            merged_player["startgg_id"] = player_row.startgg_id
        if player_row.parrygg_id:
            merged_player["parrygg_id"] = player_row.parrygg_id
        merged_players.append(merged_player)

    if merged_players:
        merged_payload["players"] = merged_players

    if source_row is None:
        source_row = SourceMetadata(source_name=source_name, metadata_override=merged_payload)
    else:
        source_row.metadata_override = merged_payload
    db.add(source_row)

    return merged_payload


def _session_started_without_completion(source_name: str) -> bool:
    with _stream_state_lock:
        source_row = _source_connections.get(source_name)
        if source_row is None:
            return False

        connected_at = source_row.get("connected_at")
        if connected_at is None:
            return False

        last_completed_at = source_row.get("last_completed_at")
        return last_completed_at is None or last_completed_at < connected_at


def _record_stream_event(source_name: str, username: str, repository: str, filename: str, status: str) -> None:
    global _stream_event_sequence

    event_time = datetime.now(timezone.utc)
    with _stream_state_lock:
        _stream_event_sequence += 1
        _recent_events.appendleft(
            {
                "event_id": _stream_event_sequence,
                "source_name": source_name,
                "username": username,
                "repository": repository,
                "filename": filename,
                "status": status,
                "timestamp": event_time,
            }
        )

        if source_name in _source_connections:
            _source_connections[source_name]["updated_at"] = event_time
            _source_connections[source_name]["last_activity_at"] = event_time
            _source_connections[source_name]["stream_phase"] = status
            if status in {"completed", "ended"}:
                _source_connections[source_name]["last_completed_at"] = event_time


def get_stream_status_snapshot(source_names: set[str] | None = None) -> dict[str, list[dict]]:
    with _stream_state_lock:
        sources = list(_source_connections.values())
        events = list(_recent_events)

    if source_names is not None:
        sources = [source for source in sources if source["source_name"] in source_names]
        events = [event for event in events if event["source_name"] in source_names]

    # Treat recent completed events as live activity for stream status.
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    events = [event for event in events if event["timestamp"] >= cutoff]

    return {
        "sources": sources,
        "events": events,
    }


def get_stream_events_since(last_event_id: int, source_names: set[str] | None = None) -> list[dict]:
    with _stream_state_lock:
        events = list(_recent_events)

    if source_names is not None:
        events = [event for event in events if event.get("source_name") in source_names]

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    events = [event for event in events if event.get("timestamp") and event["timestamp"] >= cutoff]

    filtered = [event for event in events if int(event.get("event_id", 0)) > last_event_id]
    filtered.sort(key=lambda event: int(event.get("event_id", 0)))
    return filtered


def _authenticate_ftp_credentials(
    username: str,
    token_value: str,
    session_factory=SessionLocal,
) -> FTPSessionContext:
    normalized_username = username.strip()
    if not normalized_username or not token_value:
        raise AuthenticationFailed("Missing username or source token")

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
            raise AuthenticationFailed("Invalid source token")

        repositories = {repo.name for repo in token_row.repositories}
        if not repositories:
            raise AuthenticationFailed("Source token has no repository access")

        if len(repositories) == 1:
            repository_name = next(iter(repositories))
        else:
            tournament_repo_names = {
                tournament.repository.name
                for tournament in token_row.tournaments
                if tournament.repository and tournament.repository.name
            }
            if len(tournament_repo_names) != 1:
                raise AuthenticationFailed(
                    "Source token must map to exactly one repository for FTP uploads"
                )
            repository_name = next(iter(tournament_repo_names))

        return FTPSessionContext(
            user_id=user.id,
            token_id=token_row.id,
            username=user.username,
            source_name=token_row.source_name,
            repositories=repositories,
            repository_name=repository_name,
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

        authorizer = SourceTokenAuthorizer()
        handler_cls = ReplayFTPHandler
        handler_cls.authorizer = authorizer
        print(f"[FTP] Using handler class: {handler_cls.__name__}", flush=True)

        masquerade_address = settings.FTP_MASQUERADE_ADDRESS.strip()
        if masquerade_address:
            handler_cls.masquerade_address = masquerade_address

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
