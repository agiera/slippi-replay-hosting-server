#!/usr/bin/env python3

from __future__ import annotations

import io
import json
import time
from pathlib import Path


def upload_metadata_sidecar(ftp, replay_filename: str, ubjson_hex: str) -> None:
    sidecar_json = json.dumps({"ubjson_hex": ubjson_hex}).encode("utf-8")
    sidecar_filename = replay_filename + ".meta.json"
    ftp.storbinary(f"STOR {sidecar_filename}", io.BytesIO(sidecar_json))


def upload_metadata_sidecar_file(ftp, replay_filename: str, sidecar_path: Path) -> None:
    sidecar_filename = replay_filename + ".meta.json"
    ftp.storbinary(f"STOR {sidecar_filename}", io.BytesIO(sidecar_path.read_bytes()))


def _paced_bytes_io(payload: bytes, chunk_bytes: int, chunk_delay_seconds: float) -> io.BytesIO:
    if chunk_delay_seconds <= 0:
        return io.BytesIO(payload)

    class PacedBytesIO(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            capped_size = chunk_bytes if size < 0 else min(size, chunk_bytes)
            data = super().read(capped_size)
            if data and self.tell() < len(payload):
                time.sleep(chunk_delay_seconds)
            return data

    return PacedBytesIO(payload)


def upload_replay_bytes(
    ftp,
    filename: str,
    payload: bytes,
    *,
    chunk_bytes: int = 8192,
    chunk_delay_seconds: float = 0,
) -> None:
    fileobj = _paced_bytes_io(payload, chunk_bytes, chunk_delay_seconds)
    ftp.storbinary(f"STOR {filename}", fileobj, blocksize=chunk_bytes)


def upload_replay_file_once(
    ftp,
    path: Path,
    sidecar_path: Path | None,
    *,
    ubjson_hex: str | None = None,
    upload_chunk_bytes: int = 8192,
    upload_chunk_delay_seconds: float = 0,
) -> None:
    filename = path.name
    if sidecar_path is not None:
        upload_metadata_sidecar_file(ftp, filename, sidecar_path)
    elif ubjson_hex:
        upload_metadata_sidecar(ftp, filename, ubjson_hex)

    upload_replay_bytes(
        ftp,
        filename,
        path.read_bytes(),
        chunk_bytes=upload_chunk_bytes,
        chunk_delay_seconds=upload_chunk_delay_seconds,
    )