#!/usr/bin/env python3
"""Batch-update Wii Slippi FTP password in slippi_console.dat files.

This script updates the fixed-size ftp_password field in each
slippi_console.dat file under a root directory.

Field layout (from slippi_settings struct):
- ftp_password offset: 138
- ftp_password size:   32 bytes (31 chars + NUL typical)

Usage examples:
  python3 scripts/batch_patch_wii_ftp_password.py \
    --root /run/media/agiera --new-token "slp_12345678901234567890123456"

  python3 scripts/batch_patch_wii_ftp_password.py \
    --root /run/media/agiera --new-token "slp_..." --old-token "slp_old..."

  python3 scripts/batch_patch_wii_ftp_password.py \
    --root /run/media/agiera --new-token "slp_..." --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path

FTP_PASSWORD_OFFSET = 138
FTP_PASSWORD_FIELD_SIZE = 32
MAX_TOKEN_LEN = 30
TARGET_NAME = "slippi_console.dat"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch replace ftp_password in slippi_console.dat files"
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Root directory to scan recursively (example: /run/media/agiera)",
    )
    parser.add_argument(
        "--new-token",
        required=True,
        help=f"New FTP password/token (max {MAX_TOKEN_LEN} chars)",
    )
    parser.add_argument(
        "--old-token",
        default=None,
        help="Optional: only replace if current token exactly matches this value",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )
    return parser.parse_args()


def validate_token(label: str, token: str | None) -> str | None:
    if token is None:
        return None
    if "\x00" in token:
        raise ValueError(f"{label} contains NUL byte")
    try:
        token.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} must be ASCII") from exc
    if len(token) > MAX_TOKEN_LEN:
        raise ValueError(f"{label} too long: {len(token)} > {MAX_TOKEN_LEN}")
    return token


def read_field(raw: bytes) -> str:
    # Field is NUL-terminated in a fixed-size byte slot.
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")


def encode_field(token: str) -> bytes:
    encoded = token.encode("ascii")
    return encoded + (b"\x00" * (FTP_PASSWORD_FIELD_SIZE - len(encoded)))


def find_targets(root: Path) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(f"Root path does not exist: {root}")
    return sorted(p for p in root.rglob(TARGET_NAME) if p.is_file())


def patch_file(path: Path, new_token: str, old_token: str | None, dry_run: bool) -> tuple[bool, str, str]:
    data = path.read_bytes()

    min_size = FTP_PASSWORD_OFFSET + FTP_PASSWORD_FIELD_SIZE
    if len(data) < min_size:
        raise ValueError(f"File too small ({len(data)} bytes), expected at least {min_size}")

    old_raw = data[FTP_PASSWORD_OFFSET : FTP_PASSWORD_OFFSET + FTP_PASSWORD_FIELD_SIZE]
    current = read_field(old_raw)

    if old_token is not None and current != old_token:
        return (False, current, current)

    if current == new_token:
        return (False, current, current)

    if not dry_run:
        new_raw = encode_field(new_token)
        patched = bytearray(data)
        patched[FTP_PASSWORD_OFFSET : FTP_PASSWORD_OFFSET + FTP_PASSWORD_FIELD_SIZE] = new_raw
        path.write_bytes(bytes(patched))

    return (True, current, new_token)


def mask(value: str) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 6:
        return "*" * len(value)
    return value[:4] + "..." + value[-2:]


def main() -> int:
    args = parse_args()

    new_token = validate_token("--new-token", args.new_token)
    old_token = validate_token("--old-token", args.old_token)
    assert new_token is not None

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
            did_change, before, after = patch_file(path, new_token, old_token, args.dry_run)
            if did_change:
                changed += 1
                action = "WOULD UPDATE" if args.dry_run else "UPDATED"
                print(f"[{action}] {path}  {mask(before)} -> {mask(after)}")
            else:
                skipped += 1
                print(f"[SKIP] {path}  current={before}")
        except Exception as exc:  # noqa: BLE001
            errored += 1
            print(f"[ERROR] {path}  {exc}")

    mode = "DRY RUN" if args.dry_run else "APPLY"
    print()
    print(f"{mode} SUMMARY: changed={changed}, skipped={skipped}, errors={errored}, scanned={len(targets)}")

    return 0 if errored == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
