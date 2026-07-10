#!/usr/bin/env python3
"""Simulate a live Slippi source over FTP for local stream UI testing.

This script connects to the backend FTP ingest server using an existing
uploader/superuser username + source token, then keeps the connection alive.

Optional: it can upload small dummy .slp files at an interval to generate
recent stream events while connected.

It can also send the backend's custom SITE SLPMETAUBJ command so metadata
override behavior can be exercised from the simulator.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from ftplib import FTP, all_errors as ftp_errors
from pathlib import Path


@dataclass
class Config:
    host: str
    port: int
    username: str
    token: str
    repository: str | None
    keepalive_seconds: float
    upload_interval_seconds: float
    upload_prefix: str
    slpmeta_ubjson_hex: str | None
    clear_slpmeta_on_exit: bool


BAKED_CONTROLLER_METADATA_BY_PORT: dict[str, dict[str, str]] = {
    "0": {
        "nametag": "TAG0",
        "name": "Player Zero",
        "slippi": "ZAUB#866",
        "smashgg": "startgg-demo-0",
        "parrygg": "parry-demo-0",
        "firmware": "1.0.0",
    },
    "1": {
        "nametag": "TAG1",
        "name": "Player One",
        "slippi": "ONE#002",
        "smashgg": "startgg-demo-1",
        "parrygg": "parry-demo-1",
        "firmware": "1.0.0",
    },
}


def parse_args() -> Config:
    parser = argparse.ArgumentParser(
        description="Simulate a live stream source via FTP for UI testing."
    )
    parser.add_argument("--host", default=os.getenv("STREAM_SIM_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("STREAM_SIM_PORT", "2121")))
    parser.add_argument(
        "--username",
        default=os.getenv("STREAM_SIM_USERNAME", ""),
        help="Uploader/superuser username for FTP auth.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("STREAM_SIM_TOKEN", ""),
        help="Source API token value used as FTP password.",
    )
    parser.add_argument(
        "--repository",
        default=os.getenv("STREAM_SIM_REPOSITORY", ""),
        help="Repository directory to CWD into after login (optional).",
    )
    parser.add_argument(
        "--keepalive-seconds",
        type=float,
        default=float(os.getenv("STREAM_SIM_KEEPALIVE", "10")),
        help="Seconds between NOOP keepalive commands.",
    )
    parser.add_argument(
        "--upload-interval-seconds",
        type=float,
        default=float(os.getenv("STREAM_SIM_UPLOAD_INTERVAL", "0")),
        help="If > 0, upload a tiny dummy .slp every N seconds.",
    )
    parser.add_argument(
        "--upload-prefix",
        default=os.getenv("STREAM_SIM_UPLOAD_PREFIX", "sim"),
        help="Filename prefix when upload interval is enabled.",
    )
    slpmeta_group = parser.add_mutually_exclusive_group()
    slpmeta_group.add_argument(
        "--slpmeta-json",
        default=os.getenv("STREAM_SIM_SLPMETA_JSON", ""),
        help="JSON metadata (players list or port-keyed object) to convert to UBJSON.",
    )
    slpmeta_group.add_argument(
        "--slpmeta-file",
        default=os.getenv("STREAM_SIM_SLPMETA_FILE", ""),
        help="Path to a JSON metadata file to convert to UBJSON.",
    )
    slpmeta_group.add_argument(
        "--slpmeta-ubjson-hex",
        default=os.getenv("STREAM_SIM_SLPMETA_UBJSON_HEX", ""),
        help="Pre-encoded UBJSON metadata payload in hex for SITE SLPMETAUBJ.",
    )
    slpmeta_group.add_argument(
        "--use-baked-slpmeta",
        action="store_true",
        default=os.getenv("STREAM_SIM_USE_BAKED_SLPMETA", "").strip().lower() in {"1", "true", "yes", "on"},
        help="Use built-in demo controller metadata and send it as SITE SLPMETAUBJ.",
    )
    parser.add_argument(
        "--clear-slpmeta-on-exit",
        action="store_true",
        default=os.getenv("STREAM_SIM_CLEAR_SLPMETA_ON_EXIT", "").strip().lower() in {"1", "true", "yes", "on"},
        help="Send SITE CLEARSLPMETA before disconnecting if SLPMETAUBJ was applied.",
    )

    args = parser.parse_args()

    if not args.username:
        parser.error("--username is required (or set STREAM_SIM_USERNAME)")
    if not args.token:
        parser.error("--token is required (or set STREAM_SIM_TOKEN)")
    if args.keepalive_seconds <= 0:
        parser.error("--keepalive-seconds must be > 0")
    if args.upload_interval_seconds < 0:
        parser.error("--upload-interval-seconds must be >= 0")

    repository = args.repository.strip() or None
    slpmeta_ubjson_hex = _load_slpmeta_ubjson_hex(
        parser,
        raw_json=args.slpmeta_json,
        json_file=args.slpmeta_file,
        ubjson_hex=args.slpmeta_ubjson_hex,
        use_baked=args.use_baked_slpmeta,
    )

    return Config(
        host=args.host,
        port=args.port,
        username=args.username,
        token=args.token,
        repository=repository,
        keepalive_seconds=args.keepalive_seconds,
        upload_interval_seconds=args.upload_interval_seconds,
        upload_prefix=args.upload_prefix,
        slpmeta_ubjson_hex=slpmeta_ubjson_hex,
        clear_slpmeta_on_exit=args.clear_slpmeta_on_exit,
    )


def _load_slpmeta_ubjson_hex(
    parser: argparse.ArgumentParser,
    raw_json: str,
    json_file: str,
    ubjson_hex: str,
    use_baked: bool,
) -> str | None:
    if use_baked:
        return _encode_ubjson_object(BAKED_CONTROLLER_METADATA_BY_PORT).hex()

    if ubjson_hex.strip():
        candidate = ubjson_hex.strip().lower()
        if len(candidate) % 2 != 0:
            parser.error("--slpmeta-ubjson-hex must have even-length hex")
        try:
            bytes.fromhex(candidate)
        except ValueError:
            parser.error("--slpmeta-ubjson-hex must be valid hex")
        return candidate

    source_text = ""
    if raw_json.strip():
        source_text = raw_json.strip()
    elif json_file.strip():
        try:
            source_text = Path(json_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            parser.error(f"unable to read --slpmeta-file: {exc}")

    if not source_text:
        return None

    try:
        payload = json.loads(source_text)
    except json.JSONDecodeError as exc:
        parser.error(f"invalid SLPMETA JSON: {exc}")

    by_port = _normalize_json_metadata_by_port(parser, payload)
    ubjson_bytes = _encode_ubjson_object(by_port)
    return ubjson_bytes.hex()


def _normalize_json_metadata_by_port(parser: argparse.ArgumentParser, payload: object) -> dict[str, dict[str, str]]:
    if not isinstance(payload, dict):
        parser.error("SLPMETA JSON must be an object")

    out: dict[str, dict[str, str]] = {}

    players = payload.get("players")
    if isinstance(players, list):
        for idx, player in enumerate(players):
            if not isinstance(player, dict):
                parser.error(f"players[{idx}] must be an object")
            if "port" not in player:
                parser.error(f"players[{idx}] requires port")
            try:
                port = int(player["port"])
            except (TypeError, ValueError):
                parser.error(f"players[{idx}].port must be an integer")
            if port < 1 or port > 4:
                parser.error(f"players[{idx}].port must be 1..4")

            normalized = _normalize_controller_metadata_fields(player)
            if normalized:
                out[str(port - 1)] = normalized

        return out

    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        try:
            parsed_port = int(str(key))
        except ValueError:
            continue
        if parsed_port < 0 or parsed_port > 3:
            continue
        normalized = _normalize_controller_metadata_fields(value)
        if normalized:
            out[str(parsed_port)] = normalized

    if out:
        return out

    parser.error("SLPMETA JSON must use players[] with port or object keys 0..3")


def _normalize_controller_metadata_fields(player_meta: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in player_meta.items():
        if key == "port" or not isinstance(value, str):
            continue

        key_norm = "".join(ch for ch in str(key).lower() if ch.isalnum())
        if key_norm in {"nametag", "tag"}:
            out["nametag"] = value
        elif key_norm in {"name", "displayname", "display"}:
            out["name"] = value
        elif key_norm in {"slippi", "slippicode", "connectcode"}:
            out["slippi"] = value
        elif key_norm in {"smashgg", "startgg"}:
            out["smashgg"] = value
        elif key_norm == "parrygg":
            out["parrygg"] = value
        elif key_norm == "firmware":
            out["firmware"] = value

    return out


def _encode_ubjson_object(value: dict[str, object]) -> bytes:
    buf = bytearray()
    buf.append(ord("{"))
    for key, inner in value.items():
        _append_ubjson_len_prefixed_ascii(buf, key)
        if isinstance(inner, dict):
            buf.extend(_encode_ubjson_object(inner))
        elif isinstance(inner, str):
            buf.append(ord("S"))
            _append_ubjson_len_prefixed_ascii(buf, inner)
        else:
            raise ValueError("UBJSON encoder only supports dict and string values")
    buf.append(ord("}"))
    return bytes(buf)


def _append_ubjson_len_prefixed_ascii(buf: bytearray, value: str) -> None:
    try:
        raw = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("Only ASCII metadata is supported for UBJSON payloads") from exc

    if len(raw) > 255:
        raise ValueError("UBJSON string too long (>255 bytes)")

    buf.append(ord("U"))
    buf.append(len(raw))
    buf.extend(raw)


def build_dummy_replay_bytes() -> bytes:
    # This is intentionally tiny and not a valid replay file. It is only
    # useful for exercising ingest/event paths in local testing.
    now = datetime.now(timezone.utc).isoformat()
    return f"SIMULATED_SLP_UPLOAD {now}\n".encode("utf-8")


def connect_ftp(cfg: Config) -> FTP:
    ftp = FTP()
    ftp.connect(host=cfg.host, port=cfg.port, timeout=15)
    ftp.login(user=cfg.username, passwd=cfg.token)

    if cfg.repository:
        ftp.cwd(cfg.repository)

    return ftp


def apply_slpmeta_override(ftp: FTP, cfg: Config) -> None:
    if not cfg.slpmeta_ubjson_hex:
        return

    response = ftp.sendcmd(f"SITE SLPMETAUBJ {cfg.slpmeta_ubjson_hex}")
    print(f"Applied SITE SLPMETAUBJ: {response}", flush=True)


def upload_dummy_replay(ftp: FTP, filename: str, payload: bytes) -> None:
    try:
        ftp.storbinary(f"STOR {filename}", io.BytesIO(payload))
        return
    except OSError as exc:
        passive = getattr(ftp, "passiveserver", True)
        if getattr(exc, "errno", None) == 111 and passive:
            print(
                "Passive FTP data channel was refused. Retrying upload in active mode...",
                flush=True,
            )
            ftp.set_pasv(False)
            ftp.storbinary(f"STOR {filename}", io.BytesIO(payload))
            return
        raise


def clear_slpmeta_override(ftp: FTP, cfg: Config) -> None:
    if not cfg.slpmeta_ubjson_hex or not cfg.clear_slpmeta_on_exit:
        return

    response = ftp.sendcmd("SITE CLEARSLPMETA")
    print(f"Cleared SITE SLPMETA: {response}", flush=True)


def run(cfg: Config) -> int:
    print(
        f"Connecting to FTP {cfg.host}:{cfg.port} as '{cfg.username}'...",
        flush=True,
    )
    try:
        ftp = connect_ftp(cfg)
    except ftp_errors as exc:
        print("Failed to connect/login to FTP simulator target.", file=sys.stderr)
        print(f"FTP error: {exc}", file=sys.stderr)
        print(
            "Tip: ensure FTP is enabled in backend env and port is reachable "
            "from your machine.",
            file=sys.stderr,
        )
        return 2

    try:
        apply_slpmeta_override(ftp, cfg)
    except ftp_errors as exc:
        print(f"Failed to apply SITE SLPMETAUBJ: {exc}", file=sys.stderr)
        try:
            ftp.quit()
        except Exception:
            pass
        return 3

    print("Connected. Stream source should now appear as live in the UI.", flush=True)
    if cfg.upload_interval_seconds > 0:
        print(
            f"Dummy uploads enabled every {cfg.upload_interval_seconds:g}s "
            f"with prefix '{cfg.upload_prefix}'.",
            flush=True,
        )
    else:
        print("Dummy uploads disabled (keepalive-only mode).", flush=True)
    print("Press Ctrl+C to stop simulation.", flush=True)

    should_stop = False

    def _handle_stop(_: int, __) -> None:
        nonlocal should_stop
        should_stop = True

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    next_upload_at = time.monotonic() + cfg.upload_interval_seconds if cfg.upload_interval_seconds > 0 else float("inf")

    try:
        while not should_stop:
            now = time.monotonic()

            if now >= next_upload_at:
                payload = build_dummy_replay_bytes()
                filename = f"{cfg.upload_prefix}-{int(time.time())}.slp"
                upload_dummy_replay(ftp, filename, payload)
                print(f"Uploaded dummy replay: {filename}", flush=True)
                next_upload_at = now + cfg.upload_interval_seconds

            ftp.voidcmd("NOOP")
            time.sleep(cfg.keepalive_seconds)
    except ftp_errors as exc:
        print(f"FTP connection dropped: {exc}", file=sys.stderr)
        return 4
    finally:
        try:
            clear_slpmeta_override(ftp, cfg)
        except Exception:
            pass
        try:
            ftp.quit()
        except Exception:
            pass

    print("Simulator stopped.", flush=True)
    return 0


def main() -> int:
    cfg = parse_args()
    return run(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
