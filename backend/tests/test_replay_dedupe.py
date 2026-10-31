"""Content-hash deduplication of replay uploads."""
import gzip
import hashlib

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.api_token import ApiToken
from app.models.file import File
from app.models.repository import Repository
from app.models.user import User
from app.scripts import backfill_file_sha256
from app.services import replay_upload
from app.services.replay_upload import DuplicateReplayError, persist_replay_upload

DATA = b"SLP-DATA-ONE"
DATA_HASH = hashlib.sha256(DATA).hexdigest()


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "REPLAY_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "REPLAY_VIEW_ARCHIVE_DIR", str(tmp_path / "archive"))
    monkeypatch.setattr(settings, "REPLAY_VIEW_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path


def _seed_token(db_session, *, repo_name: str, raw_token: str) -> tuple[ApiToken, Repository]:
    repo = db_session.scalar(select(Repository).where(Repository.name == repo_name))
    if repo is None:
        repo = Repository(name=repo_name, is_public=True)
        db_session.add(repo)
        db_session.commit()

    user = User(username=f"u-{raw_token}", email=f"{raw_token}@example.com", hashed_password="x", role="uploader")
    user.repositories.append(repo)
    db_session.add(user)
    db_session.commit()

    token = ApiToken(
        user_id=user.id,
        collection_name=f"src-{raw_token}",
        token_prefix=raw_token[:12],
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
    )
    token.repositories.append(repo)
    db_session.add(token)
    db_session.commit()
    return token, repo


def _upload(client, raw_token: str, data: bytes = DATA, name: str = "game.slp", headers: dict | None = None):
    return client.post(
        "/api/v1/uploads/files",
        files={"file": (name, data, "application/octet-stream")},
        headers={"X-API-Token": raw_token, **(headers or {})},
    )


def test_upload_records_hash_and_rejects_identical_bytes_with_409(client, db_session, storage):
    _seed_token(db_session, repo_name="public", raw_token="slp_dedupe_a")

    first = _upload(client, "slp_dedupe_a")
    assert first.status_code == 200
    stored = db_session.scalar(select(File).where(File._id == first.json()["id"]))
    assert stored.sha256 == DATA_HASH
    assert stored.repository_id is not None

    second = _upload(client, "slp_dedupe_a", name="renamed-copy.slp")
    assert second.status_code == 409
    body = second.json()
    assert body["detail"] == "Replay already uploaded"
    assert (body["id"], body["folder"], body["name"]) == (stored._id, stored.folder, stored.name)

    assert len(db_session.scalars(select(File)).all()) == 1
    stored_files = [p for p in (storage / "uploads").rglob("*") if p.is_file()]
    assert len(stored_files) == 1


def test_identical_bytes_are_allowed_in_different_repositories(client, db_session, storage):
    _seed_token(db_session, repo_name="public", raw_token="slp_dedupe_pub")
    _seed_token(db_session, repo_name="other", raw_token="slp_dedupe_oth")

    assert _upload(client, "slp_dedupe_pub").status_code == 200
    assert _upload(client, "slp_dedupe_oth").status_code == 200
    assert len(db_session.scalars(select(File)).all()) == 2


def test_upload_verifies_client_supplied_content_hash(client, db_session, storage):
    _seed_token(db_session, repo_name="public", raw_token="slp_dedupe_hdr")

    bad = _upload(client, "slp_dedupe_hdr", headers={"X-Content-SHA256": "0" * 64})
    assert bad.status_code == 400
    assert db_session.scalars(select(File)).all() == []

    good = _upload(client, "slp_dedupe_hdr", headers={"X-Content-SHA256": DATA_HASH.upper()})
    assert good.status_code == 200


def test_check_endpoint_reports_existing_hashes_scoped_to_repository(client, db_session, storage):
    _seed_token(db_session, repo_name="public", raw_token="slp_check_pub")
    _seed_token(db_session, repo_name="other", raw_token="slp_check_oth")
    uploaded = _upload(client, "slp_check_pub").json()
    missing = hashlib.sha256(b"never uploaded").hexdigest()

    res = client.post(
        "/api/v1/uploads/files/check",
        json={"hashes": [DATA_HASH.upper(), missing, DATA_HASH]},
        headers={"X-API-Token": "slp_check_pub"},
    )
    assert res.status_code == 200
    assert res.json() == {
        "existing": {DATA_HASH: {"id": uploaded["id"], "folder": uploaded["folder"], "name": uploaded["name"]}}
    }

    other = client.post(
        "/api/v1/uploads/files/check",
        json={"hashes": [DATA_HASH]},
        headers={"X-API-Token": "slp_check_oth"},
    )
    assert other.json() == {"existing": {}}


def test_check_endpoint_validates_input_and_requires_a_token(client, db_session, storage):
    _seed_token(db_session, repo_name="public", raw_token="slp_check_val")
    headers = {"X-API-Token": "slp_check_val"}

    assert client.post("/api/v1/uploads/files/check", json={"hashes": ["nothex"]}, headers=headers).status_code == 422
    too_many = {"hashes": [DATA_HASH] * 1001}
    assert client.post("/api/v1/uploads/files/check", json=too_many, headers=headers).status_code == 422
    assert client.post("/api/v1/uploads/files/check", json={"hashes": []}, headers=headers).json() == {"existing": {}}
    assert client.post("/api/v1/uploads/files/check", json={"hashes": [DATA_HASH]}).status_code in (401, 403)


def test_concurrent_duplicate_that_slips_past_the_check_is_still_rejected(db_session, storage, monkeypatch):
    token, _repo = _seed_token(db_session, repo_name="public", raw_token="slp_race")

    def upload():
        return persist_replay_upload(db_session, token_row=token, repository_name="public", original_name="g.slp", data=DATA)

    upload()
    db_session.commit()

    # Simulate the other request committing between our existence check and insert.
    real_find = replay_upload.find_file_by_hash
    calls = {"n": 0}

    def find_after_race(*args, **kwargs):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_find(*args, **kwargs)

    monkeypatch.setattr(replay_upload, "find_file_by_hash", find_after_race)
    with pytest.raises(DuplicateReplayError):
        upload()

    assert len(db_session.scalars(select(File)).all()) == 1
    stored_files = [p for p in (storage / "uploads").rglob("*") if p.is_file()]
    assert len(stored_files) == 1, "the losing upload's file must be removed"


def test_backfill_hashes_legacy_rows_from_storage_and_archive(db_session, testing_session_local, storage, monkeypatch):
    _token, repo = _seed_token(db_session, repo_name="public", raw_token="slp_backfill")
    monkeypatch.setattr(backfill_file_sha256, "SessionLocal", testing_session_local)

    folder = "uploads/public/src/2026/01/01"
    raw_dir = storage / "uploads" / folder
    raw_dir.mkdir(parents=True)
    (raw_dir / "raw.slp").write_bytes(b"raw-bytes")
    (raw_dir / "raw-dup.slp").write_bytes(b"raw-bytes")
    archive_dir = storage / "archive" / folder
    archive_dir.mkdir(parents=True)
    with gzip.open(archive_dir / "parsed.zlp.gz", "wb") as f:
        f.write(b"original-zlp")

    rows = [
        File(folder=folder, name="raw.slp", size_bytes=9, repository_id=repo.id),
        File(folder=folder, name="raw-dup.slp", size_bytes=9, repository_id=repo.id),
        File(folder=folder, name="parsed.peppi.json.gz", size_bytes=1, repository_id=repo.id),
        File(folder=folder, name="gone.slp", size_bytes=1, repository_id=repo.id),
        File(folder="elsewhere", name="orphan.slp", size_bytes=1, repository_id=None),
    ]
    db_session.add_all(rows)
    db_session.commit()

    dry = backfill_file_sha256.run_backfill(commit=False)
    assert dry["hashed"] == 2
    db_session.expire_all()
    assert all(row.sha256 is None for row in db_session.scalars(select(File)))

    stats = backfill_file_sha256.run_backfill()
    assert {k: stats[k] for k in ("scanned", "hashed", "missing_source", "no_repository", "duplicates")} == {
        "scanned": 5, "hashed": 2, "missing_source": 1, "no_repository": 1, "duplicates": 1,
    }
    assert stats["duplicate_files"][0]["path"] == f"{folder}/raw-dup.slp"

    db_session.expire_all()
    by_name = {row.name: row.sha256 for row in db_session.scalars(select(File))}
    assert by_name["raw.slp"] == hashlib.sha256(b"raw-bytes").hexdigest()
    assert by_name["parsed.peppi.json.gz"] == hashlib.sha256(b"original-zlp").hexdigest()
    assert by_name["raw-dup.slp"] is None


def _finished_slp(payload: bytes) -> tuple[bytes, bytes]:
    """Return (bytes as streamed live, bytes of the finished file on disk)."""
    footer = b"U\x08metadata{U\x07startAtSU\x142026-01-01T00:00:00Z}}"
    streamed = b"{U\x03raw[$U#l\x00\x00\x00\x00" + payload + footer
    finished = bytearray(streamed)
    finished[11:15] = len(payload).to_bytes(4, "big")
    return streamed, bytes(finished)


def _stream(client, raw_token: str, data: bytes, name: str = "Game_live.slp"):
    return client.post(
        "/api/v1/uploads/files/stream",
        content=data,
        headers={"X-API-Token": raw_token, "X-Filename": name, "Content-Type": "application/octet-stream"},
    )


def test_streamed_game_is_hashed_like_the_finished_file(client, db_session, storage):
    _seed_token(db_session, repo_name="public", raw_token="slp_stream_hash")
    streamed, finished = _finished_slp(b"frame-bytes")

    res = _stream(client, "slp_stream_hash", streamed)
    assert res.status_code == 200
    stored = db_session.scalar(select(File).where(File._id == res.json()["id"]))
    # The daemon records the hash of the finished file; both must agree so the
    # finished file is never uploaded a second time.
    assert stored.sha256 == hashlib.sha256(finished).hexdigest()

    assert _upload(client, "slp_stream_hash", data=finished).status_code == 409
    assert _stream(client, "slp_stream_hash", streamed).status_code == 409
    assert len(db_session.scalars(select(File)).all()) == 1


def test_stream_endpoint_validates_input(client, db_session, storage):
    _seed_token(db_session, repo_name="public", raw_token="slp_stream_val")
    assert _stream(client, "slp_stream_val", b"x", name="notes.txt").status_code == 400
    assert _stream(client, "slp_stream_val", b"").status_code == 400
    assert db_session.scalars(select(File)).all() == []
