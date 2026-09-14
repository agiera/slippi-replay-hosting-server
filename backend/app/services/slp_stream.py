"""Helpers for finalizing Slippi ``.slp`` files streamed live by console mirroring.

Slippi writes the ``raw`` element length as a zero placeholder while a game is in
progress and only backfills the real length once the game ends and the UBJSON
``metadata`` object is appended (closing the root object). These helpers detect
completeness and repair the header so peppi can parse the received bytes, whether
the transfer captured a finished game or was cut short.

The byte layout mirrors the sequential-write format handled by the Wii FTP path
in :mod:`app.services.ftp_server`.
"""

# Header emitted for a live/sequential write: the 4-byte ``raw`` length is zero
# and only backfilled once the game finishes.
STREAMED_SLP_HEADER = b"{U\x03raw[$U#l\x00\x00\x00\x00"
# Appearance of the UBJSON ``metadata`` key marks the end-of-game footer.
SLP_METADATA_MARKER = b"U\x08metadata"
_SLP_METADATA_FOOTER_PREFIX = b"U\x08metadata{U\x07startAtSU"


def is_streamed_slp(data: bytes) -> bool:
    return data.startswith(STREAMED_SLP_HEADER)


def is_slp_complete(data: bytes) -> bool:
    """True once the UBJSON container is closed (metadata footer written)."""
    if not data.startswith(STREAMED_SLP_HEADER):
        # A non-streamed header already carries its real raw length.
        return True
    return SLP_METADATA_MARKER in data


def finalize_streamed_slp_raw_length(data: bytes) -> bytes:
    """Backfill the raw byte count left blank by sequential live writes."""
    if not data.startswith(STREAMED_SLP_HEADER):
        return data

    footer_offset = data.rfind(_SLP_METADATA_FOOTER_PREFIX)
    if footer_offset < len(STREAMED_SLP_HEADER):
        raise ValueError("streamed SLP is missing its metadata footer")

    raw_length = footer_offset - len(STREAMED_SLP_HEADER)
    if raw_length > 0x7FFFFFFF:
        raise ValueError("streamed SLP raw data is too large")

    finalized = bytearray(data)
    finalized[11:15] = raw_length.to_bytes(4, byteorder="big", signed=False)
    return bytes(finalized)


def patch_partial_slp_raw_length(data: bytes) -> bytes:
    """Treat all received bytes as raw payload so an unfinished game still parses."""
    if not data.startswith(STREAMED_SLP_HEADER) or len(data) <= len(STREAMED_SLP_HEADER):
        return data

    raw_length = min(len(data) - len(STREAMED_SLP_HEADER), 0x7FFFFFFF)
    patched = bytearray(data)
    patched[11:15] = int(raw_length).to_bytes(4, byteorder="big", signed=False)
    return bytes(patched)


def finalize_streamed_slp(data: bytes) -> bytes:
    """Repair a streamed ``.slp`` header for parsing, complete or partial.

    A finished game is repaired against its metadata footer; a game cut short
    (client timeout or disconnect) has its placeholder length set to whatever
    payload arrived so peppi can still read the frames that were captured.
    """
    if not data.startswith(STREAMED_SLP_HEADER):
        return data
    if SLP_METADATA_MARKER in data:
        return finalize_streamed_slp_raw_length(data)
    return patch_partial_slp_raw_length(data)
