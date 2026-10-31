"""Backfill File.sha256 and recording identity for replays stored before
content-hash deduplication (sha256, game_key, is_partial, source_size_bytes).

The hash is of the replay bytes as originally uploaded. Parsed replays are stored
converted (``.peppi.json.gz``), so their original bytes are read from the view
archive; unparsed replays are stored as uploaded and hashed directly.

Rows whose hash already belongs to another file in the same repository are true
duplicates; they are left unhashed and reported so they can be reviewed.

Usage: python -m app.scripts.backfill_file_sha256 [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from sqlalchemy import or_, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.file import File
from app.services.replay_identity import identify_slp
from app.services.replay_upload import compute_content_hash
from app.services.view_cache import PEPPI_SUFFIX


def original_replay_bytes(row: File) -> bytes | None:
    if row.name.endswith(PEPPI_SUFFIX):
        stem = row.name[: -len(PEPPI_SUFFIX)]
        for suffix in (".slp", ".zlp"):
            archive_path = Path(settings.REPLAY_VIEW_ARCHIVE_DIR) / row.folder / f"{stem}{suffix}.gz"
            if archive_path.is_file():
                return gzip.decompress(archive_path.read_bytes())
        return None

    stored_path = Path(settings.REPLAY_STORAGE_DIR) / row.folder / row.name
    if stored_path.is_file():
        return stored_path.read_bytes()
    return None


def run_backfill(limit: int | None = None, commit: bool = True) -> dict:
    stats = {"scanned": 0, "hashed": 0, "identified": 0, "missing_source": 0, "no_repository": 0, "duplicates": 0}
    duplicates: list[dict] = []

    with SessionLocal() as db:
        # source_size_bytes is set for every processed row, so it marks rows whose
        # identity columns still need filling.
        query = select(File).where(or_(File.sha256.is_(None), File.source_size_bytes.is_(None))).order_by(File._id)
        if limit is not None:
            query = query.limit(limit)
        rows = list(db.scalars(query))

        # Hashes already claimed per repository, from earlier rows and this run.
        claimed: dict[tuple[int, str], int] = {
            (repo_id, sha): file_id
            for file_id, repo_id, sha in db.execute(
                select(File._id, File.repository_id, File.sha256).where(File.sha256.is_not(None))
            )
        }

        for row in rows:
            stats["scanned"] += 1
            if row.repository_id is None:
                stats["no_repository"] += 1
                continue

            data = original_replay_bytes(row)
            if data is None:
                stats["missing_source"] += 1
                continue

            if row.source_size_bytes is None:
                identity = identify_slp(data)
                row.source_size_bytes = len(data)
                row.game_key = identity.game_key if identity else None
                row.is_partial = identity.is_partial if identity else None
                stats["identified"] += 1

            if row.sha256 is None:
                content_hash = compute_content_hash(data)
                key = (row.repository_id, content_hash)
                if key in claimed:
                    stats["duplicates"] += 1
                    duplicates.append(
                        {"file_id": row._id, "duplicate_of": claimed[key], "path": f"{row.folder}/{row.name}"}
                    )
                else:
                    claimed[key] = row._id
                    row.sha256 = content_hash
                    stats["hashed"] += 1

            if commit and stats["scanned"] % 200 == 0:
                db.commit()

        if commit:
            db.commit()
        else:
            db.rollback()

    stats["duplicate_files"] = duplicates
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill File.sha256 content hashes")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N unhashed files")
    parser.add_argument("--dry-run", action="store_true", help="Run without committing changes")
    args = parser.parse_args()

    stats = run_backfill(limit=args.limit, commit=not args.dry_run)
    print(json.dumps(stats, separators=(",", ":")))


if __name__ == "__main__":
    main()
