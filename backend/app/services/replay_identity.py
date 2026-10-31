"""Identify which recording a ``.slp`` belongs to, and whether it is complete.

A live stream cut short (client quit, network drop) is stored as a partial copy;
the complete file for the same recording arrives later as different bytes, so the
content hash cannot relate them. Every copy of one recording, however, starts
with identical bytes: the Event Payloads table followed by the Game Start event,
which includes the game's random seed. Hashing that prefix gives a key shared by
the partial and complete copies of a recording.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

SLP_RAW_PREFIX = b"{U\x03raw[$U#l"
_RAW_START = len(SLP_RAW_PREFIX) + 4
_METADATA_KEY = b"U\x08metadata"
_EVENT_PAYLOADS = 0x35
_GAME_START = 0x36


@dataclass(frozen=True)
class ReplayIdentity:
    game_key: str
    is_partial: bool


def _game_start_end(data: bytes) -> int | None:
    """Offset just past the Game Start event, or None if not fully present."""
    if len(data) < _RAW_START + 2 or data[_RAW_START] != _EVENT_PAYLOADS:
        return None
    payload_size = data[_RAW_START + 1]
    table_end = _RAW_START + 1 + payload_size
    if payload_size < 1 or (payload_size - 1) % 3 or len(data) < table_end + 1:
        return None

    sizes = {}
    for offset in range(_RAW_START + 2, table_end, 3):
        sizes[data[offset]] = int.from_bytes(data[offset + 1 : offset + 3], "big")

    if data[table_end] != _GAME_START or _GAME_START not in sizes:
        return None
    end = table_end + 1 + sizes[_GAME_START]
    return end if len(data) >= end else None


def identify_slp(data: bytes) -> ReplayIdentity | None:
    """Return the recording key and completeness of an uncompressed ``.slp``.

    Returns None for other formats or when the Game Start event hasn't been
    received yet. A replay is complete when its metadata block immediately
    follows the raw event data, as only happens once the game has ended and the
    header's raw length was written.
    """
    if not data.startswith(SLP_RAW_PREFIX):
        return None
    game_start_end = _game_start_end(data)
    if game_start_end is None:
        return None

    raw_length = int.from_bytes(data[len(SLP_RAW_PREFIX) : _RAW_START], "big")
    footer_offset = _RAW_START + raw_length
    is_complete = raw_length > 0 and data[footer_offset : footer_offset + len(_METADATA_KEY)] == _METADATA_KEY
    return ReplayIdentity(
        game_key=hashlib.sha256(data[_RAW_START:game_start_end]).hexdigest(),
        is_partial=not is_complete,
    )
