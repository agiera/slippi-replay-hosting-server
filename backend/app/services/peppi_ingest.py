from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import gzip
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import peppi_py


@dataclass
class ParsedReplayData:
    stage: int | None
    start_time: str | None
    last_frame: int | None
    is_teams: int
    players: list[dict[str, Any]]
    peppi_bytes: bytes
    end_method: str | None = None


def parse_slippi_bytes(data: bytes, suffix: str = ".slp") -> ParsedReplayData:
    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        temp_path = Path(tmp.name)

    try:
        try:
            game = peppi_py.read_slippi(str(temp_path), skip_frames=True, allow_incomplete=True)
        except TypeError:
            # Backward-compatible path for older peppi-py versions.
            game = peppi_py.read_slippi(str(temp_path), skip_frames=True)
    finally:
        temp_path.unlink(missing_ok=True)

    metadata = game.metadata or {}
    trailer_metadata = _extract_metadata_from_slp_tail(data)
    if trailer_metadata:
        if not isinstance(metadata, dict):
            metadata = trailer_metadata
        else:
            merged = dict(metadata)
            for key, value in trailer_metadata.items():
                if merged.get(key) is None:
                    merged[key] = value
            metadata = merged

    start_time = metadata.get("startAt") if isinstance(metadata, dict) else None
    last_frame = _coerce_int(metadata.get("lastFrame")) if isinstance(metadata, dict) else None
    if last_frame is None:
        # Some replays omit metadata.lastFrame but still include an end frame.
        last_frame = _coerce_int(getattr(getattr(game, "end", None), "frame", None))
    end_method = _normalize_end_method(getattr(getattr(game, "end", None), "method", None))
    winners_by_port = _extract_winners_by_port(game)

    # Extract controller firmware metadata (PhobGCC etc) written by nintendont
    # to the SLP footer under metadata["players"]["0..3"].  Key is 0-indexed
    # channel, value is a flat UBJSON string dict from the controller.
    footer_ctrl_meta = _extract_footer_controller_metadata(metadata)

    players = []
    for player in game.start.players:
        port = _port_to_int(player.port)
        netplay = player.netplay
        ctrl = footer_ctrl_meta.get(port, {})
        players.append(
            {
                "port": port,
                "type": _coerce_player_type(player.type),
                "character_id": _coerce_int(player.character),
                "connect_code": (netplay.code if netplay else None) or ctrl.get("slippi_code"),
                "display_name": (netplay.name if netplay else None) or ctrl.get("display_name"),
                "tag": player.name_tag or ctrl.get("tag"),
                "user_id": netplay.suid if netplay else None,
                "startgg_id": ctrl.get("startgg_id"),
                "parrygg_id": ctrl.get("parrygg_id"),
                "is_winner": winners_by_port.get(port),
            }
        )

    peppi_payload = {
        "start": _to_jsonable(game.start),
        "end": _to_jsonable(game.end),
        "metadata": _to_jsonable(metadata),
    }
    peppi_bytes = gzip.compress(
        json.dumps(peppi_payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"),
        compresslevel=9,
    )

    return ParsedReplayData(
        stage=_coerce_int(game.start.stage),
        start_time=start_time,
        last_frame=last_frame,
        is_teams=1 if game.start.is_teams else 0,
        players=players,
        peppi_bytes=peppi_bytes,
        end_method=end_method,
    )


_CONTROLLER_METADATA_PORT_KEYS = {"port", "playerport", "playerindex"}


def _controller_metadata_port_from_field(raw_port: object) -> int | None:
    """Port taken from an explicit controller-metadata field.

    A 1..4 value is the in-game port as authored; a 0..3 value is treated as a
    0-indexed SI channel.
    """
    try:
        parsed = int(str(raw_port).strip())
    except (TypeError, ValueError):
        return None
    if 1 <= parsed <= 4:
        return parsed
    if 0 <= parsed <= 3:
        return parsed + 1
    return None


def _controller_metadata_port_from_key(raw_key: object) -> int | None:
    """Port derived from the UBJSON object key, a 0-indexed SI channel."""
    try:
        channel = int(str(raw_key).strip())
    except (TypeError, ValueError):
        return None
    if 0 <= channel <= 3:
        return channel + 1
    return None


def normalize_controller_metadata_players(raw_players: Any) -> dict[int, dict[str, str]]:
    """Normalise a UBJSON ``players`` object into ``{port: normalised fields}``.

    Shared by the live FTP streaming sidecar and the completed SLP footer parse so
    both derive the player port identically. The port is taken from an explicit
    ``port`` field inside each player's controller-metadata dict when present, and
    otherwise falls back to the object key (a 0-indexed SI channel -> 1-indexed
    port).
    """
    result: dict[int, dict[str, str]] = {}
    if not isinstance(raw_players, dict):
        return result

    for key, player_meta in raw_players.items():
        if not isinstance(player_meta, dict):
            continue

        normalized: dict[str, str] = {}
        port_from_field: int | None = None
        for field, value in player_meta.items():
            key_norm = "".join(ch for ch in str(field).lower() if ch.isalnum())
            if key_norm in _CONTROLLER_METADATA_PORT_KEYS:
                if port_from_field is None:
                    port_from_field = _controller_metadata_port_from_field(value)
                continue
            if not isinstance(value, str):
                continue
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

        port = port_from_field if port_from_field is not None else _controller_metadata_port_from_key(key)
        if port is None:
            continue
        if not normalized:
            continue
        result[port] = normalized

    return result


def _extract_footer_controller_metadata(metadata: Any) -> dict[int, dict[str, str]]:
    """Extract PhobGCC/firmware controller metadata from the SLP footer players block.

    SlippiFileWriter writes metadata["players"] as a UBJSON object keyed by
    controller channel ("0".."3"); each value is a flat string dict from the
    controller firmware. Returns a mapping of 1-indexed port -> normalised fields.
    """
    if not isinstance(metadata, dict):
        return {}
    return normalize_controller_metadata_players(metadata.get("players"))


def _extract_metadata_from_slp_tail(data: bytes) -> dict[str, Any] | None:
    if not data:
        return None

    marker = b"metadata{"
    marker_pos = data.rfind(marker)
    if marker_pos < 0:
        return None

    obj_start = marker_pos + len(b"metadata")
    if obj_start >= len(data) or data[obj_start] != ord("{"):
        return None

    try:
        decoded, _ = _parse_ubjson_object(data, obj_start)
    except Exception:
        return None

    if not isinstance(decoded, dict):
        return None
    return decoded


def _parse_ubjson_object(data: bytes, start: int) -> tuple[dict[str, Any], int]:
    if start >= len(data) or data[start] != ord("{"):
        raise ValueError("expected object opener")

    pos = start + 1
    out: dict[str, Any] = {}
    while True:
        if pos >= len(data):
            raise ValueError("unterminated object")
        if data[pos] == ord("}"):
            return out, pos + 1

        key, pos = _parse_ubjson_string(data, pos)
        value, pos = _parse_ubjson_value(data, pos)
        out[key] = value


def _parse_ubjson_value(data: bytes, start: int) -> tuple[Any, int]:
    if start >= len(data):
        raise ValueError("missing value marker")

    marker = data[start]
    if marker == ord("{"):
        return _parse_ubjson_object(data, start)
    if marker == ord("S"):
        return _parse_ubjson_string(data, start + 1)
    if marker == ord("U"):
        return data[start + 1], start + 2
    if marker == ord("i"):
        raw = data[start + 1]
        return (raw - 256 if raw > 127 else raw), start + 2
    if marker == ord("l"):
        if start + 5 > len(data):
            raise ValueError("truncated int32")
        return int.from_bytes(data[start + 1:start + 5], byteorder="big", signed=True), start + 5
    if marker == ord("T"):
        return True, start + 1
    if marker == ord("F"):
        return False, start + 1
    if marker == ord("Z"):
        return None, start + 1

    raise ValueError(f"unsupported value marker: {chr(marker)!r}")


def _parse_ubjson_string(data: bytes, start: int) -> tuple[str, int]:
    length, pos = _parse_ubjson_length(data, start)
    end = pos + length
    if end > len(data):
        raise ValueError("truncated string")
    return data[pos:end].decode("utf-8", errors="replace"), end


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


@dataclass
class ParsedReplayStart:
    stage: int | None
    players: list[dict[str, Any]]


def parse_slippi_start_partial(data: bytes, suffix: str = ".slp") -> ParsedReplayStart | None:
    """Extract stage and the start-of-game player list from a possibly-incomplete SLP.

    The Game Start event sits at the very beginning of an SLP stream, so this works
    on a partial upload that is still being transferred. It returns the same player
    identity/character/type data the completed parse produces (minus winner info,
    which is only known once the game ends). Returns None if no start block is found.
    """
    if not data:
        return None

    prefix_sizes = [len(data), 512 * 1024, 256 * 1024, 128 * 1024, 64 * 1024, 32 * 1024, 16 * 1024]
    tried: set[int] = set()

    for size in prefix_sizes:
        size = min(size, len(data))
        if size <= 0 or size in tried:
            continue
        tried.add(size)

        with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data[:size])
            temp_path = Path(tmp.name)

        try:
            try:
                game = peppi_py.read_slippi(str(temp_path), skip_frames=True, allow_incomplete=True)
            except TypeError:
                game = peppi_py.read_slippi(str(temp_path), skip_frames=True)
        except Exception:
            continue
        finally:
            temp_path.unlink(missing_ok=True)

        start = getattr(game, "start", None)
        if start is None:
            continue

        stage = _coerce_int(getattr(start, "stage", None))
        players: list[dict[str, Any]] = []
        for player in getattr(start, "players", None) or []:
            port = _port_to_int(player.port)
            netplay = getattr(player, "netplay", None)
            player_type = _coerce_player_type(player.type)
            players.append(
                {
                    "port": port,
                    "type": player_type,
                    "is_cpu": player_type == 1,
                    "character_id": _coerce_int(player.character),
                    "connect_code": netplay.code if netplay else None,
                    "display_name": netplay.name if netplay else None,
                    "tag": player.name_tag or None,
                }
            )

        if players or stage is not None:
            return ParsedReplayStart(stage=stage, players=players)

    return None


def parse_slippi_stage_partial(data: bytes, suffix: str = ".slp") -> int | None:
    """Best-effort stage extraction from potentially incomplete/corrupt replay bytes.

    Attempts peppi parsing on progressively smaller prefixes so stage can still be
    recovered when full replay parsing fails.
    """

    if not data:
        return None

    prefix_sizes = [len(data), 256 * 1024, 128 * 1024, 64 * 1024, 32 * 1024, 16 * 1024, 8 * 1024]
    tried: set[int] = set()

    for size in prefix_sizes:
        size = min(size, len(data))
        if size <= 0 or size in tried:
            continue
        tried.add(size)

        with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data[:size])
            temp_path = Path(tmp.name)

        try:
            game = peppi_py.read_slippi(str(temp_path), skip_frames=True)
            stage = _coerce_int(getattr(getattr(game, "start", None), "stage", None))
            if stage is not None:
                return stage
        except Exception:
            continue
        finally:
            temp_path.unlink(missing_ok=True)

    return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _port_to_int(port: Any) -> int | None:
    if isinstance(port, Enum) and str(port.name).startswith("P"):
        return _coerce_int(str(port.name)[1:])
    if isinstance(port, str) and port.startswith("P"):
        return _coerce_int(port[1:])
    value = _coerce_int(port)
    if value is None:
        return None
    # Some libraries encode P1 as 0; normalize to 1-based DB ports.
    return value + 1 if value in {0, 1, 2, 3} else value


def _coerce_player_type(value: Any) -> int | None:
    if isinstance(value, Enum):
        lookup = {"HUMAN": 0, "CPU": 1, "DEMO": 2}
        return lookup.get(value.name)
    return _coerce_int(value)


def _extract_winners_by_port(game: Any) -> dict[int, int]:
    end = getattr(game, "end", None)
    players_end = getattr(end, "players", None) if end else None
    if not players_end:
        return {}

    placements = []
    for player_end in players_end:
        placement = _coerce_int(getattr(player_end, "placement", None))
        port = _port_to_int(getattr(player_end, "port", None))
        if placement is None or port is None:
            continue
        placements.append((port, placement))

    if not placements:
        return {}

    min_placement = min(placement for _, placement in placements)
    return {port: 1 if placement == min_placement else 0 for port, placement in placements}


def _normalize_end_method(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.name).upper()
    text = str(value).strip()
    return text.upper() if text else None


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.name
    if is_dataclass(value):
        return {field.name: _to_jsonable(getattr(value, field.name)) for field in fields(type(value))}
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value
