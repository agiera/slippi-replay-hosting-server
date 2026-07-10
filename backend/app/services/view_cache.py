from __future__ import annotations

import gzip
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

PEPPI_SUFFIX = ".peppi.json.gz"

_last_pruned_at: datetime | None = None


def _cache_root() -> Path:
    root = Path(settings.REPLAY_VIEW_CACHE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _archive_root() -> Path:
    root = Path(settings.REPLAY_VIEW_ARCHIVE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _strip_peppi_suffix(name: str) -> str:
    if name.endswith(PEPPI_SUFFIX):
        return name[: -len(PEPPI_SUFFIX)]
    return Path(name).stem


def cache_view_replay_bytes(folder_rel: str, canonical_name: str, original_suffix: str, data: bytes) -> Path | None:
    if not canonical_name.endswith(PEPPI_SUFFIX):
        return None

    suffix = (original_suffix or ".slp").lower()
    if suffix not in {".slp", ".zlp"}:
        suffix = ".slp"

    cache_name = f"{_strip_peppi_suffix(canonical_name)}{suffix}"
    cache_path = _cache_root() / folder_rel / cache_name
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(data)
    return cache_path


def archive_view_replay_bytes(folder_rel: str, canonical_name: str, original_suffix: str, data: bytes) -> Path | None:
    if not canonical_name.endswith(PEPPI_SUFFIX):
        return None

    suffix = (original_suffix or ".slp").lower()
    if suffix not in {".slp", ".zlp"}:
        suffix = ".slp"

    archive_name = f"{_strip_peppi_suffix(canonical_name)}{suffix}.gz"
    archive_path = _archive_root() / folder_rel / archive_name
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(archive_path, "wb", compresslevel=9) as f:
        f.write(data)

    return archive_path


def get_cached_replay_path(folder_rel: str, canonical_name: str) -> Path | None:
    if not canonical_name.endswith(PEPPI_SUFFIX):
        return None

    base = _strip_peppi_suffix(canonical_name)
    root = _cache_root() / folder_rel
    for suffix in (".slp", ".zlp"):
        candidate = root / f"{base}{suffix}"
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def rebuild_cached_replay_from_archive(folder_rel: str, canonical_name: str) -> Path | None:
    if not canonical_name.endswith(PEPPI_SUFFIX):
        return None

    base = _strip_peppi_suffix(canonical_name)
    archive_root = _archive_root() / folder_rel

    for suffix in (".slp", ".zlp"):
        archive_path = archive_root / f"{base}{suffix}.gz"
        if not archive_path.exists() or not archive_path.is_file():
            continue

        cache_path = _cache_root() / folder_rel / f"{base}{suffix}"
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        with gzip.open(archive_path, "rb") as src, open(cache_path, "wb") as dst:
            dst.write(src.read())

        return cache_path

    return None


def prune_view_cache(force: bool = False) -> None:
    global _last_pruned_at

    now = datetime.now(timezone.utc)
    interval = max(0, int(settings.REPLAY_VIEW_CACHE_PRUNE_INTERVAL_SECONDS))
    ttl = max(0, int(settings.REPLAY_VIEW_CACHE_TTL_SECONDS))

    if not force and _last_pruned_at is not None:
        elapsed = (now - _last_pruned_at).total_seconds()
        if elapsed < interval:
            return

    root = _cache_root()
    cutoff = now.timestamp() - ttl

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            continue

    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass

    _last_pruned_at = now
