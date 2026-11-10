"""Decoder for ``.slpz`` uploads: compressed Slippi streams sent by the Wii firmware.

An ``.slpz`` body is a raw DEFLATE stream (RFC 1951, no zlib header) whose inflated
bytes are the usual streamed ``.slp`` with one reversible transform applied inside
the ``raw`` element, to pre-frame (0x37) and post-frame (0x38) events only:

- payload bytes ``0..3`` (frame number) are XORed with the same bytes of the
  previous event with the same command;
- if the payload is at most ``DELTA_MAX_PAYLOAD`` bytes, bytes ``6..`` are XORed
  with the previous event of the same command, player index (payload byte 4) and
  follower flag (payload byte 5). The first such event per slot is sent as-is.

The transform stops at the first byte that is not a known command, i.e. the
metadata footer.

Must match kernel/SlippiCompress.c in slippi-nintendont.
"""

from __future__ import annotations

import logging
import zlib
from typing import BinaryIO

logger = logging.getLogger(__name__)

SLPZ_SUFFIX = ".slpz"
HEADER_LEN = 15
DELTA_MAX_PAYLOAD = 128
DELTA_FIRST_BYTE = 6
_PRE_FRAME, _POST_FRAME = 0x37, 0x38

_HEADER, _EXPECT_CMD, _SIZES_LEN, _SIZES, _IN_EVENT, _PASS = range(6)


class SlpzError(ValueError):
    """The upload is not a valid slpz stream."""


class DeltaDecoder:
    """Undo the per-player XOR delta, one byte at a time across arbitrary chunking."""

    def __init__(self) -> None:
        self._state = _HEADER
        self._pos = 0
        self._sizes: dict[int, int] = {}
        self._cmd = 0
        self._remaining = 0
        self._index = 0
        self._player = 0
        self._slot: int | None = None
        self._triplet = bytearray()
        self._prev: dict[int, bytearray] = {}
        self._frame = [bytearray(4), bytearray(4)]
        self._have: set[int] = set()

    def feed(self, data: bytes) -> bytes:
        out = bytearray(data)
        for i, byte in enumerate(out):
            state = self._state
            if state == _PASS:
                return bytes(out)
            if state == _HEADER:
                self._pos += 1
                if self._pos == HEADER_LEN:
                    self._state = _EXPECT_CMD
            elif state == _EXPECT_CMD:
                self._start_event(byte)
            elif state == _SIZES_LEN:
                self._sizes[0x35] = byte
                self._remaining = byte - 1
                self._triplet.clear()
                self._state = _SIZES if self._remaining > 0 else _EXPECT_CMD
            elif state == _SIZES:
                self._triplet.append(byte)
                if len(self._triplet) == 3:
                    self._sizes[self._triplet[0]] = (self._triplet[1] << 8) | self._triplet[2]
                    self._triplet.clear()
                self._remaining -= 1
                if self._remaining == 0:
                    self._state = _EXPECT_CMD
            else:
                out[i] = self._event_byte(byte)
        return bytes(out)

    def _start_event(self, cmd: int) -> None:
        if not self._sizes:
            self._state = _SIZES_LEN if cmd == 0x35 else _PASS
            return
        size = self._sizes.get(cmd)
        if not size:
            self._state = _PASS
            return
        self._cmd = cmd
        self._remaining = size
        self._index = 0
        self._slot = None
        self._state = _IN_EVENT

    def _event_byte(self, byte: int) -> int:
        index = self._index
        if self._cmd in (_PRE_FRAME, _POST_FRAME):
            if index < 4:
                frame = self._frame[self._cmd - _PRE_FRAME]
                byte ^= frame[index]
                frame[index] = byte
            elif index == 4:
                self._player = byte
            elif index == 5:
                if self._player < 4 and byte < 2 and self._sizes[self._cmd] <= DELTA_MAX_PAYLOAD:
                    self._slot = (self._cmd - _PRE_FRAME) * 8 + self._player * 2 + byte
            elif index >= DELTA_FIRST_BYTE and self._slot is not None:
                prev = self._prev.setdefault(self._slot, bytearray(DELTA_MAX_PAYLOAD))
                if self._slot in self._have:
                    byte ^= prev[index]
                prev[index] = byte
        self._index += 1
        self._remaining -= 1
        if self._remaining == 0:
            if self._slot is not None:
                self._have.add(self._slot)
            self._state = _EXPECT_CMD
        return byte


class SlpzDecoder:
    """Incremental slpz -> slp decoder."""

    def __init__(self) -> None:
        self._inflate = zlib.decompressobj(-15)
        self._delta = DeltaDecoder()
        self.bytes_in = 0
        self.bytes_out = 0

    @property
    def complete(self) -> bool:
        return self._inflate.eof

    def feed(self, data: bytes) -> bytes:
        self.bytes_in += len(data)
        if self._inflate.eof:
            return b""
        try:
            inflated = self._inflate.decompress(data)
        except zlib.error as exc:
            raise SlpzError(str(exc)) from exc
        out = self._delta.feed(inflated)
        self.bytes_out += len(out)
        return out

    def flush(self) -> bytes:
        try:
            inflated = self._inflate.flush()
        except zlib.error as exc:
            raise SlpzError(str(exc)) from exc
        out = self._delta.feed(inflated)
        self.bytes_out += len(out)
        return out


def decode_slpz(data: bytes) -> bytes:
    decoder = SlpzDecoder()
    return decoder.feed(data) + decoder.flush()


class SlpzDecodingFile:
    """Wrap a staged upload file so received slpz bytes land on disk as plain slp.

    Corrupt input stops decoding but never fails the transfer; the bytes decoded so
    far stay on disk and the normal truncated-stream handling takes over.
    """

    def __init__(self, fd: BinaryIO) -> None:
        self._fd = fd
        self.decoder = SlpzDecoder()
        self.failed = False

    @property
    def name(self) -> str:
        return self._fd.name

    @property
    def closed(self) -> bool:
        return self._fd.closed

    def write(self, data: bytes) -> int:
        if not self.failed:
            try:
                self._fd.write(self.decoder.feed(data))
            except SlpzError as exc:
                self.failed = True
                logger.error("[FTP][ERROR] Corrupt slpz stream '%s': %s", self.name, exc)
        return len(data)

    def close(self) -> None:
        if self._fd.closed:
            return
        if not self.failed:
            try:
                self._fd.write(self.decoder.flush())
            except SlpzError as exc:
                self.failed = True
                logger.error("[FTP][ERROR] Corrupt slpz stream '%s': %s", self.name, exc)
        self._fd.close()
        d = self.decoder
        logger.info(
            "[FTP][UPLOAD] slpz '%s' in=%d out=%d ratio=%.2f complete=%s",
            self.name, d.bytes_in, d.bytes_out, d.bytes_out / d.bytes_in if d.bytes_in else 0.0, d.complete,
        )
