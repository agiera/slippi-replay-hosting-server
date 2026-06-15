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


def parse_slippi_bytes(data: bytes, suffix: str = ".slp") -> ParsedReplayData:
    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        temp_path = Path(tmp.name)

    try:
        game = peppi_py.read_slippi(str(temp_path), skip_frames=True)
    finally:
        temp_path.unlink(missing_ok=True)

    metadata = game.metadata or {}
    start_time = metadata.get("startAt") if isinstance(metadata, dict) else None
    last_frame = _coerce_int(metadata.get("lastFrame")) if isinstance(metadata, dict) else None
    winners_by_port = _extract_winners_by_port(game)

    players = []
    for player in game.start.players:
        port = _port_to_int(player.port)
        netplay = player.netplay
        players.append(
            {
                "port": port,
                "type": _coerce_player_type(player.type),
                "character_id": _coerce_int(player.character),
                "connect_code": netplay.code if netplay else None,
                "display_name": netplay.name if netplay else None,
                "tag": player.name_tag,
                "user_id": netplay.suid if netplay else None,
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
    )


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
