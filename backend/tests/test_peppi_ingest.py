from app.services.peppi_ingest import _extract_metadata_from_slp_tail


def _ubjson_len(value: int) -> bytes:
    return b"U" + bytes([value])


def _ubjson_str(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return b"S" + _ubjson_len(len(encoded)) + encoded


def _ubjson_key(key: str) -> bytes:
    encoded = key.encode("utf-8")
    return _ubjson_len(len(encoded)) + encoded


def _ubjson_int32(value: int) -> bytes:
    return b"l" + int(value).to_bytes(4, byteorder="big", signed=True)


def test_extract_metadata_from_slp_tail_parses_start_and_last_frame() -> None:
    metadata_obj = (
        b"{"
        + _ubjson_key("startAt")
        + _ubjson_str("2012-01-22T10:24:50")
        + _ubjson_key("lastFrame")
        + _ubjson_int32(1041)
        + _ubjson_key("players")
        + b"{}"
        + _ubjson_key("playedOn")
        + _ubjson_str("nintendont")
        + b"}"
    )
    payload = b"\x00\x01replay-bytes..." + _ubjson_key("metadata") + metadata_obj + b"\x02\x03"

    parsed = _extract_metadata_from_slp_tail(payload)

    assert parsed is not None
    assert parsed["startAt"] == "2012-01-22T10:24:50"
    assert parsed["lastFrame"] == 1041
    assert parsed["playedOn"] == "nintendont"


def test_extract_metadata_from_slp_tail_returns_none_when_missing() -> None:
    assert _extract_metadata_from_slp_tail(b"plain slp bytes without metadata marker") is None
