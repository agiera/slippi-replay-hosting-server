from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.file import File
from app.models.game import Game
from app.services.peppi_ingest import parse_slippi_bytes
from app.services.view_cache import get_cached_replay_path, rebuild_cached_replay_from_archive


_FILENAME_TS_RE = re.compile(r"^(\d{8}T\d{6})Z(?:_|\.)")


def _coerce_iso_utc(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _start_time_from_filename(name: str) -> str | None:
    match = _FILENAME_TS_RE.match(name or "")
    if not match:
        return None
    try:
        parsed = datetime.strptime(match.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return parsed.isoformat().replace("+00:00", "Z")


def _extract_from_peppi_archive(path: Path) -> tuple[str | None, int | None, int | None, int]:
    payload = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    metadata = payload.get("metadata") or {}
    start = payload.get("start") or {}
    end = payload.get("end") or {}

    start_time = metadata.get("startAt") if isinstance(metadata, dict) else None
    last_frame_raw = metadata.get("lastFrame") if isinstance(metadata, dict) else None
    if last_frame_raw is None and isinstance(end, dict):
        last_frame_raw = end.get("frame")
    stage_raw = start.get("stage") if isinstance(start, dict) else None
    is_teams_raw = start.get("is_teams") if isinstance(start, dict) else False

    last_frame = int(last_frame_raw) if last_frame_raw is not None else None
    stage = int(stage_raw) if stage_raw is not None else None
    is_teams = 1 if bool(is_teams_raw) else 0
    return start_time, last_frame, stage, is_teams


def _extract_from_raw_replay(path: Path) -> tuple[str | None, int | None, int | None, int] | None:
    suffix = path.suffix
    if suffix not in {".slp", ".zlp"}:
        return None

    try:
        parsed = parse_slippi_bytes(path.read_bytes(), suffix=suffix)
    except Exception:
        return None

    return parsed.start_time, parsed.last_frame, parsed.stage, parsed.is_teams


def _extract_from_peppi_raw_cache(folder: str, canonical_name: str) -> tuple[str | None, int | None, int | None, int] | None:
    cached = get_cached_replay_path(folder, canonical_name)
    if not cached:
        cached = rebuild_cached_replay_from_archive(folder, canonical_name)
    if not cached or not cached.exists() or not cached.is_file():
        return None

    try:
        parsed = parse_slippi_bytes(cached.read_bytes(), suffix=cached.suffix)
    except Exception:
        return None

    return parsed.start_time, parsed.last_frame, parsed.stage, parsed.is_teams


def run_backfill(limit: int | None = None, commit: bool = True) -> dict[str, int]:
    stats = {
        "scanned": 0,
        "updated": 0,
        "created_games": 0,
        "skipped_missing_file": 0,
        "skipped_unparsed": 0,
    }

    storage_root = Path(settings.REPLAY_STORAGE_DIR)

    with SessionLocal() as db:
        stmt = (
            select(File, Game)
            .select_from(File)
            .outerjoin(Game, Game.file_id == File._id)
            .order_by(File._id.asc())
        )
        rows = db.execute(stmt).all()

        if limit is not None:
            rows = rows[: max(0, limit)]

        for file_row, game_row in rows:
            stats["scanned"] += 1

            needs_backfill = (
                game_row is None
                or game_row.start_time is None
                or game_row.last_frame is None
            )
            if not needs_backfill:
                continue

            path = storage_root / file_row.folder / file_row.name
            if not path.exists() or not path.is_file():
                stats["skipped_missing_file"] += 1
                continue

            extracted: tuple[str | None, int | None, int | None, int] | None = None
            if file_row.name.endswith(".peppi.json.gz"):
                try:
                    extracted = _extract_from_peppi_archive(path)
                except Exception:
                    extracted = None

                if extracted is not None:
                    start_time, last_frame, stage, is_teams = extracted
                    if start_time is None or last_frame is None:
                        raw_extracted = _extract_from_peppi_raw_cache(file_row.folder, file_row.name)
                        if raw_extracted is not None:
                            raw_start_time, raw_last_frame, raw_stage, raw_is_teams = raw_extracted
                            extracted = (
                                start_time or raw_start_time,
                                last_frame if last_frame is not None else raw_last_frame,
                                stage if stage is not None else raw_stage,
                                is_teams if is_teams is not None else raw_is_teams,
                            )
            else:
                extracted = _extract_from_raw_replay(path)

            if extracted is None:
                stats["skipped_unparsed"] += 1
                continue

            start_time, last_frame, stage, is_teams = extracted
            fallback_start_time = (
                _coerce_iso_utc(file_row.birth_time)
                or _start_time_from_filename(file_row.name)
            )
            resolved_start_time = start_time or fallback_start_time
            if game_row is None:
                game_row = Game(
                    file_id=file_row._id,
                    is_ranked=0,
                    is_teams=is_teams,
                    stage=stage,
                    start_time=resolved_start_time,
                    last_frame=last_frame,
                )
                db.add(game_row)
                stats["created_games"] += 1
                stats["updated"] += 1
                continue

            changed = False
            if game_row.start_time is None and resolved_start_time is not None:
                game_row.start_time = resolved_start_time
                changed = True
            if game_row.last_frame is None and last_frame is not None:
                game_row.last_frame = last_frame
                changed = True
            if game_row.stage is None and stage is not None:
                game_row.stage = stage
                changed = True

            if changed:
                db.add(game_row)
                stats["updated"] += 1

        if commit:
            db.commit()
        else:
            db.rollback()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill missing replay start_time/last_frame values")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N files")
    parser.add_argument("--dry-run", action="store_true", help="Run without committing changes")
    args = parser.parse_args()

    stats = run_backfill(limit=args.limit, commit=not args.dry_run)
    print(json.dumps(stats, separators=(",", ":")))


if __name__ == "__main__":
    main()
