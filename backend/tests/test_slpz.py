import io
import random
import struct
import zlib
from pathlib import Path

from app.services import ftp_server
from app.services.ftp_server import FTPSessionContext, ReplayFTPHandler
from app.services.slpz import (
    DELTA_FIRST_BYTE,
    DELTA_MAX_PAYLOAD,
    HEADER_LEN,
    SlpzDecodingFile,
    decode_slpz,
)

HEADER = b"{U\x03raw[$U#l\x00\x00\x00\x00"
FOOTER = b"U\x08metadata{U\x07startAtSU\x142026-11-04T00:00:00Z}}"


def _event_sizes(pre: int = 0x40, post: int = 0x54) -> dict[int, int]:
    return {0x36: 0x1A0, 0x37: pre, 0x38: post, 0x39: 0x0A, 0x3A: 0x0C, 0x3B: 0x2C, 0x3C: 0x08}


def _synthetic_slp(frames: int = 120, *, pre: int = 0x40, post: int = 0x54, seed: int = 1) -> bytes:
    rng = random.Random(seed)
    sizes = _event_sizes(pre, post)
    table = b"".join(struct.pack(">BH", cmd, size) for cmd, size in sizes.items())
    raw = bytearray([0x35, len(table) + 1]) + table
    raw += bytes([0x36]) + bytes(rng.randrange(256) for _ in range(sizes[0x36]))
    state = {key: bytearray(rng.randrange(256) for _ in range(64)) for key in [(p, f) for p in (0, 1) for f in (0, 1)]}
    for frame in range(-123, -123 + frames):
        raw += bytes([0x3A]) + struct.pack(">i", frame) + bytes(sizes[0x3A] - 4)
        for cmd in (0x37, 0x38):
            for (player, follower), noise in state.items():
                payload = bytearray(sizes[cmd])
                payload[0:4] = struct.pack(">i", frame)
                payload[4], payload[5] = player, follower
                for i in range(DELTA_FIRST_BYTE, len(payload)):
                    payload[i] = noise[i % len(noise)]
                noise[rng.randrange(len(noise))] = rng.randrange(256)
                raw += bytes([cmd]) + payload
        if frame % 7 == 0:
            raw += bytes([0x3B]) + bytes(rng.randrange(256) for _ in range(sizes[0x3B]))
        raw += bytes([0x3C]) + struct.pack(">ii", frame, frame)
    return HEADER + bytes(raw) + FOOTER


def _delta_encode(slp: bytes) -> bytes:
    """Reference encoder transform; mirrors kernel/SlippiCompress.c."""
    out = bytearray(slp[:HEADER_LEN])
    raw = slp[HEADER_LEN:]
    assert raw[0] == 0x35
    sizes = {0x35: raw[1]}
    for j in range(2, 1 + raw[1], 3):
        sizes[raw[j]] = (raw[j + 1] << 8) | raw[j + 2]
    prev: dict[int, bytes] = {}
    prev_frame = {0x37: bytes(4), 0x38: bytes(4)}
    pos = 0
    while pos < len(raw):
        cmd = raw[pos]
        size = sizes.get(cmd)
        if not size:
            out += raw[pos:]
            break
        payload = bytearray(raw[pos + 1:pos + 1 + size])
        original = bytes(payload)
        if cmd in (0x37, 0x38):
            for i in range(4):
                payload[i] ^= prev_frame[cmd][i]
            prev_frame[cmd] = original[:4]
        if cmd in (0x37, 0x38) and size <= DELTA_MAX_PAYLOAD and payload[4] < 4 and payload[5] < 2:
            slot = (cmd - 0x37) * 8 + payload[4] * 2 + payload[5]
            if slot in prev:
                for i in range(DELTA_FIRST_BYTE, size):
                    payload[i] ^= prev[slot][i]
            prev[slot] = original
        out += bytes([cmd]) + payload
        pos += 1 + size
    return bytes(out)


def _encode_slpz(slp: bytes, chunk: int = 2000) -> bytes:
    transformed = _delta_encode(slp)
    comp = zlib.compressobj(6, zlib.DEFLATED, -12, 8, zlib.Z_FIXED)
    out = bytearray()
    for i in range(0, len(transformed), chunk):
        out += comp.compress(transformed[i:i + chunk]) + comp.flush(zlib.Z_SYNC_FLUSH)
    return bytes(out + comp.flush())


def test_slpz_round_trips_and_compresses():
    slp = _synthetic_slp()
    encoded = _encode_slpz(slp)

    assert decode_slpz(encoded) == slp
    assert len(encoded) * 3 < len(slp)


def test_delta_transform_changes_player_frames():
    slp = _synthetic_slp(frames=4)
    assert _delta_encode(slp) != slp


def test_slpz_decodes_across_arbitrary_chunk_boundaries():
    slp = _synthetic_slp(frames=40, seed=7)
    encoded = _encode_slpz(slp, chunk=777)
    rng = random.Random(3)
    sink = io.BytesIO()
    sink.name = "Game_x.slp"
    writer = SlpzDecodingFile(sink)
    pos = 0
    while pos < len(encoded):
        step = rng.randrange(1, 64)
        writer.write(encoded[pos:pos + step])
        pos += step
    data = sink.getvalue()
    writer.close()

    assert data == slp
    assert writer.decoder.complete


def test_oversized_frame_payloads_pass_through_without_delta():
    slp = _synthetic_slp(frames=10, post=DELTA_MAX_PAYLOAD + 4)
    assert decode_slpz(_encode_slpz(slp)) == slp


def test_truncated_slpz_keeps_decoded_prefix():
    slp = _synthetic_slp(frames=60)
    encoded = _encode_slpz(slp, chunk=1000)
    sink = io.BytesIO()
    sink.name = "Game_cut.slp"
    writer = SlpzDecodingFile(sink)
    writer.write(encoded[: len(encoded) // 2])
    decoded = sink.getvalue()

    assert decoded and slp.startswith(decoded)
    assert not writer.decoder.complete


def test_corrupt_slpz_marks_failed_without_raising(caplog):
    sink = io.BytesIO()
    sink.name = "Game_bad.slp"
    writer = SlpzDecodingFile(sink)
    with caplog.at_level("ERROR", logger="app.services.slpz"):
        assert writer.write(b"\xff" * 32) == 32
        writer.write(b"\x00" * 8)
        writer.close()

    assert writer.failed
    assert writer.closed
    assert "Corrupt slpz stream" in caplog.text


def test_stor_slpz_stages_plain_slp_and_wraps_upload(monkeypatch, tmp_path):
    from pyftpdlib.handlers import FTPHandler

    handler = ReplayFTPHandler.__new__(ReplayFTPHandler)
    handler.ftp_session = FTPSessionContext(1, 1, "ftpuser", "wii-test", {"public"}, "public", str(tmp_path))
    handler._session_seen_stor_file_keys = set()
    handler._session_stor_started_monotonic = {}
    handler._session_upload_context_by_file_key = {}
    handler._session_replay_transfer_attempted = False
    handler._session_started_event_emitted = True
    handler.data_channel = None
    monkeypatch.setattr(ftp_server.settings, "FTP_STAGING_DIR", str(tmp_path))
    monkeypatch.setattr(ftp_server, "_set_source_active_staged_file", lambda *a, **k: None)
    monkeypatch.setattr(handler, "_current_source_state", lambda: {})
    started = []
    monkeypatch.setattr(handler, "_start_live_partial_parse", lambda path, source: started.append(path))

    def fake_stor(self, file, mode="w"):
        self._in_dtp_queue = (open(file, mode + "b"), "STOR")

    monkeypatch.setattr(FTPHandler, "ftp_STOR", fake_stor)

    handler.ftp_STOR(str(tmp_path / "Game_x.slpz"))

    fd, cmd = handler._in_dtp_queue
    assert isinstance(fd, SlpzDecodingFile)
    assert Path(fd.name).name == "Game_x.slp"
    assert started == [tmp_path / "Game_x.slp"]
    assert handler._session_seen_stor_file_keys == {"Game_x.slp"}

    slp = _synthetic_slp(frames=8)
    fd.write(_encode_slpz(slp))
    fd.close()
    assert (tmp_path / "Game_x.slp").read_bytes() == slp
