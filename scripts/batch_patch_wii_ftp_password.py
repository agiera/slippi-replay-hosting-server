#!/usr/bin/env python3
"""Batch-update Wii Slippi FTP password and/or server IP in slippi_console.dat files.

This script updates the fixed-size ftp_password and ftp_server fields in each
slippi_console.dat file under a root directory.

Field layout (from struct slippi_settings in slippi-wiiconf/source/Slippi.h):
- ftp_server offset:   40,  size 64 bytes (NUL-terminated string)
- ftp_password offset: 138, size 32 bytes (31 chars + NUL typical)

Usage examples:
  python3 scripts/batch_patch_wii_ftp_password.py \
    --root /run/media/agiera --new-token "slp_12345678901234567890123456"

  python3 scripts/batch_patch_wii_ftp_password.py \
    --root /run/media/agiera --new-token "slp_..." --old-token "slp_old..."

  python3 scripts/batch_patch_wii_ftp_password.py \
    --root /run/media/agiera --new-token "slp_..." --dry-run

  python3 scripts/batch_patch_wii_ftp_password.py \
    --root /run/media/agiera --new-ip 192.168.1.50

  # Read-only: show current IP and unmasked token for every file
  python3 scripts/batch_patch_wii_ftp_password.py \
    --root /run/media/agiera --show-ip --show-token

  python3 scripts/batch_patch_wii_ftp_password.py \
    --root /run/media/agiera --new-ip 10.0.0.5 --old-ip 192.168.1.100 \
    --new-token "slp_..."
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

TARGET_NAME = "slippi_console.dat"


@dataclass(frozen=True)
class Field:
    name: str
    offset: int
    size: int
    secret: bool

    @property
    def max_len(self) -> int:
        # Leave room for the trailing NUL.
        return self.size - 2 if self.secret else self.size - 1


FTP_SERVER = Field("ftp_server", offset=40, size=64, secret=False)
FTP_PASSWORD = Field("ftp_password", offset=138, size=32, secret=True)
MAX_TOKEN_LEN = FTP_PASSWORD.max_len


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch replace ftp_password and/or ftp_server in slippi_console.dat files"
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Root directory to scan recursively (example: /run/media/agiera)",
    )
    parser.add_argument(
        "--new-token",
        default=None,
        help=f"New FTP password/token (max {MAX_TOKEN_LEN} chars)",
    )
    parser.add_argument(
        "--old-token",
        default=None,
        help="Optional: only replace the token if the current one exactly matches this value",
    )
    parser.add_argument(
        "--new-ip",
        default=None,
        help=f"New FTP server IP/hostname (max {FTP_SERVER.max_len} chars)",
    )
    parser.add_argument(
        "--old-ip",
        default=None,
        help="Optional: only replace the IP if the current one exactly matches this value",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )
    parser.add_argument(
        "--show-ip",
        action="store_true",
        help="Print the current ftp_server value in full (read-only if no --new-* given)",
    )
    parser.add_argument(
        "--show-token",
        action="store_true",
        help="Print the FTP password/token unmasked (read-only if no --new-* given)",
    )
    args = parser.parse_args()
    if (
        args.new_token is None
        and args.new_ip is None
        and not args.show_ip
        and not args.show_token
    ):
        parser.error(
            "at least one of --new-token, --new-ip, --show-token or --show-ip is required"
        )
    if args.old_token is not None and args.new_token is None:
        parser.error("--old-token requires --new-token")
    if args.old_ip is not None and args.new_ip is None:
        parser.error("--old-ip requires --new-ip")
    return args


def validate_value(label: str, value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    if "\x00" in value:
        raise ValueError(f"{label} contains NUL byte")
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} must be ASCII") from exc
    if len(value) > max_len:
        raise ValueError(f"{label} too long: {len(value)} > {max_len}")
    return value


def read_field(data: bytes, field: Field) -> str:
    # Field is NUL-terminated in a fixed-size byte slot.
    raw = data[field.offset : field.offset + field.size]
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")


def encode_field(value: str, field: Field) -> bytes:
    encoded = value.encode("ascii")
    return encoded + (b"\x00" * (field.size - len(encoded)))


def find_targets(root: Path) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(f"Root path does not exist: {root}")
    return sorted(p for p in root.rglob(TARGET_NAME) if p.is_file())


def patch_file(
    path: Path,
    updates: list[tuple[Field, str, str | None]],
    dry_run: bool,
) -> list[tuple[Field, str, str]]:
    """Apply (field, new_value, old_value_filter) updates.

    Returns the (field, before, after) changes that were (or would be) made.
    """
    data = path.read_bytes()

    min_size = max(f.offset + f.size for f, _, _ in updates)
    if len(data) < min_size:
        raise ValueError(f"File too small ({len(data)} bytes), expected at least {min_size}")

    patched = bytearray(data)
    changes: list[tuple[Field, str, str]] = []
    for field, new_value, old_value in updates:
        current = read_field(data, field)
        if old_value is not None and current != old_value:
            continue
        if current == new_value:
            continue
        patched[field.offset : field.offset + field.size] = encode_field(new_value, field)
        changes.append((field, current, new_value))

    if changes and not dry_run:
        path.write_bytes(bytes(patched))

    return changes


def mask(value: str) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 6:
        return "*" * len(value)
    return value[:4] + "..." + value[-2:]


def display(field: Field, value: str, reveal: bool = False) -> str:
    if field.secret and not reveal:
        return mask(value)
    return value or "<empty>"


def main() -> int:
    args = parse_args()

    try:
        new_token = validate_value("--new-token", args.new_token, FTP_PASSWORD.max_len)
        old_token = validate_value("--old-token", args.old_token, FTP_PASSWORD.max_len)
        new_ip = validate_value("--new-ip", args.new_ip, FTP_SERVER.max_len)
        old_ip = validate_value("--old-ip", args.old_ip, FTP_SERVER.max_len)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 2

    updates: list[tuple[Field, str, str | None]] = []
    if new_token is not None:
        updates.append((FTP_PASSWORD, new_token, old_token))
    if new_ip is not None:
        updates.append((FTP_SERVER, new_ip, old_ip))

    revealed = {FTP_PASSWORD} if args.show_token else set()

    def fmt(field: Field, value: str) -> str:
        return display(field, value, reveal=field in revealed)

    # Fields to report on skip/read-only: anything being updated or explicitly shown.
    report_fields = [f for f, _, _ in updates]
    if args.show_ip and FTP_SERVER not in report_fields:
        report_fields.append(FTP_SERVER)
    if args.show_token and FTP_PASSWORD not in report_fields:
        report_fields.append(FTP_PASSWORD)

    root = Path(args.root)
    targets = find_targets(root)

    if not targets:
        print(f"No {TARGET_NAME} files found under: {root}")
        return 1

    changed = 0
    skipped = 0
    errored = 0

    for path in targets:
        try:
            if not updates:
                data = path.read_bytes()
                for f in report_fields:
                    if len(data) < f.offset + f.size:
                        raise ValueError(f"File too small ({len(data)} bytes)")
                current = "  ".join(
                    f"{f.name}={fmt(f, read_field(data, f))}" for f in report_fields
                )
                print(f"[SHOW] {path}  {current}")
                continue
            changes = patch_file(path, updates, args.dry_run)
            if changes:
                changed += 1
                action = "WOULD UPDATE" if args.dry_run else "UPDATED"
                detail = "  ".join(
                    f"{f.name}: {fmt(f, before)} -> {fmt(f, after)}"
                    for f, before, after in changes
                )
                print(f"[{action}] {path}  {detail}")
            else:
                skipped += 1
                data = path.read_bytes()
                current = "  ".join(
                    f"{f.name}={fmt(f, read_field(data, f))}" for f in report_fields
                )
                print(f"[SKIP] {path}  current: {current}")
        except Exception as exc:  # noqa: BLE001
            errored += 1
            print(f"[ERROR] {path}  {exc}")

    if not updates:
        print()
        print(f"SHOW SUMMARY: errors={errored}, scanned={len(targets)}")
        return 0 if errored == 0 else 2

    mode = "DRY RUN" if args.dry_run else "APPLY"
    print()
    print(f"{mode} SUMMARY: changed={changed}, skipped={skipped}, errors={errored}, scanned={len(targets)}")

    return 0 if errored == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
