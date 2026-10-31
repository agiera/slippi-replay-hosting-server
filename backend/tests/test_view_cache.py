"""On-disk view cache and archive of original replay bytes."""
import os
import time

import pytest

from app.core.config import settings
from app.services import view_cache
from app.services.view_cache import (
    archive_view_replay_bytes,
    archive_view_replay_sidecar_bytes,
    cache_view_replay_bytes,
    get_cached_replay_path,
    prune_view_cache,
    rebuild_cached_replay_from_archive,
    replay_artifact_paths,
)

FOLDER = "uploads/public/src/2026/01/01"
NAME = "game.peppi.json.gz"


@pytest.fixture()
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "REPLAY_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "REPLAY_VIEW_ARCHIVE_DIR", str(tmp_path / "archive"))
    monkeypatch.setattr(settings, "REPLAY_VIEW_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(view_cache, "_last_pruned_at", None)
    return tmp_path


def test_cache_and_archive_round_trip_the_original_bytes(dirs):
    cached = cache_view_replay_bytes(FOLDER, NAME, ".ZLP", b"original")
    archived = archive_view_replay_bytes(FOLDER, NAME, ".zlp", b"original")
    assert cached.name == "game.zlp" and archived.name == "game.zlp.gz"
    assert get_cached_replay_path(FOLDER, NAME) == cached

    cached.unlink()
    assert get_cached_replay_path(FOLDER, NAME) is None
    rebuilt = rebuild_cached_replay_from_archive(FOLDER, NAME)
    assert rebuilt == cached and rebuilt.read_bytes() == b"original"


def test_unparsed_replays_are_never_cached(dirs):
    assert cache_view_replay_bytes(FOLDER, "game.slp", ".slp", b"x") is None
    assert archive_view_replay_bytes(FOLDER, "game.slp", ".slp", b"x") is None
    assert rebuild_cached_replay_from_archive(FOLDER, "game.slp") is None
    assert replay_artifact_paths(FOLDER, "game.slp") == [dirs / "uploads" / FOLDER / "game.slp"]


def test_unknown_suffix_is_cached_as_slp(dirs):
    assert cache_view_replay_bytes(FOLDER, NAME, ".bin", b"x").name == "game.slp"


def test_artifact_paths_cover_everything_written_for_a_parsed_replay(dirs):
    stored = dirs / "uploads" / FOLDER / NAME
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"peppi")
    written = {
        stored,
        cache_view_replay_bytes(FOLDER, NAME, ".slp", b"x"),
        archive_view_replay_bytes(FOLDER, NAME, ".slp", b"x"),
        archive_view_replay_sidecar_bytes(FOLDER, NAME, ".slp", b"{}"),
    }
    assert written <= set(replay_artifact_paths(FOLDER, NAME))


def test_prune_removes_expired_cache_files_and_empty_dirs_but_not_the_archive(dirs, monkeypatch):
    monkeypatch.setattr(settings, "REPLAY_VIEW_CACHE_TTL_SECONDS", 60)
    old = cache_view_replay_bytes(FOLDER, NAME, ".slp", b"old")
    new = cache_view_replay_bytes("uploads/other", NAME, ".slp", b"new")
    archived = archive_view_replay_bytes(FOLDER, NAME, ".slp", b"old")
    stale = time.time() - 3600
    os.utime(old, (stale, stale))

    prune_view_cache(force=True)

    assert not old.exists() and not old.parent.exists()
    assert new.exists() and archived.exists()


def test_prune_is_rate_limited_unless_forced(dirs, monkeypatch):
    monkeypatch.setattr(settings, "REPLAY_VIEW_CACHE_TTL_SECONDS", 0)
    monkeypatch.setattr(settings, "REPLAY_VIEW_CACHE_PRUNE_INTERVAL_SECONDS", 3600)
    prune_view_cache()
    cached = cache_view_replay_bytes(FOLDER, NAME, ".slp", b"x")
    stale = time.time() - 10
    os.utime(cached, (stale, stale))

    prune_view_cache()
    assert cached.exists(), "within the prune interval"
    prune_view_cache(force=True)
    assert not cached.exists()
