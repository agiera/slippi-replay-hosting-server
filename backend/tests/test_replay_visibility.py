import time

from app.core.security import create_download_signature
from app.models.file import File
from app.models.repository import Repository
from app.models.user import User


def _seed_repos_and_files(db):
    db.add(Repository(name="openrepo", is_public=True))
    db.add(Repository(name="secretclub", is_public=False))
    public_file = File(folder="openrepo/WII-01", name="public.slp", size_bytes=10)
    private_file = File(folder="secretclub/WII-02", name="private.slp", size_bytes=10)
    db.add(public_file)
    db.add(private_file)
    db.commit()
    return public_file._id, private_file._id


def _signup(client, username="alice"):
    res = client.post(
        "/api/v1/auth/signup",
        json={"username": username, "email": f"{username}@example.com", "password": "password123"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def test_private_repo_hidden_from_anonymous(client, db_session):
    public_id, private_id = _seed_repos_and_files(db_session)

    filters = client.get("/api/v1/replays/filters").json()
    assert "openrepo" in filters["repositories"]
    assert "secretclub" not in filters["repositories"]

    listing = client.get("/api/v1/replays/files").json()
    listed_ids = {item["id"] for item in listing["items"]}
    assert public_id in listed_ids
    assert private_id not in listed_ids

    res = client.get(f"/api/v1/replays/files/{private_id}/download")
    assert res.status_code == 404


def test_member_sees_private_repo_with_signed_download_url(client, db_session):
    public_id, private_id = _seed_repos_and_files(db_session)
    token = _signup(client)

    user = db_session.query(User).filter(User.username == "alice").one()
    secret_repo = db_session.query(Repository).filter(Repository.name == "secretclub").one()
    user.repositories.append(secret_repo)
    db_session.commit()

    headers = {"Authorization": f"Bearer {token}"}

    filters = client.get("/api/v1/replays/filters", headers=headers).json()
    assert "secretclub" in filters["repositories"]

    listing = client.get("/api/v1/replays/files", headers=headers).json()
    items_by_id = {item["id"]: item for item in listing["items"]}
    assert private_id in items_by_id

    private_url = items_by_id[private_id]["download_url"]
    assert "exp=" in private_url and "sig=" in private_url

    public_url = items_by_id[public_id]["download_url"]
    assert "sig=" not in public_url


def test_non_member_user_cannot_see_private_repo(client, db_session):
    _, private_id = _seed_repos_and_files(db_session)
    token = _signup(client, username="mallory")
    headers = {"Authorization": f"Bearer {token}"}

    filters = client.get("/api/v1/replays/filters", headers=headers).json()
    assert "secretclub" not in filters["repositories"]

    listing = client.get("/api/v1/replays/files", headers=headers).json()
    assert private_id not in {item["id"] for item in listing["items"]}

    res = client.get(f"/api/v1/replays/files/{private_id}/download", headers=headers)
    assert res.status_code == 404


def test_signed_url_allows_anonymous_download(client, db_session, tmp_path, monkeypatch):
    from app.core.config import settings

    storage_root = tmp_path / "storage"
    replay_path = storage_root / "secretclub" / "WII-02" / "private.slp"
    replay_path.parent.mkdir(parents=True)
    replay_path.write_bytes(b"slippi-bytes")
    monkeypatch.setattr(settings, "REPLAY_STORAGE_DIR", str(storage_root))

    _, private_id = _seed_repos_and_files(db_session)

    exp = int(time.time()) + 60
    sig = create_download_signature(private_id, exp)

    res = client.get(f"/api/v1/replays/files/{private_id}/download?exp={exp}&sig={sig}")
    assert res.status_code == 200
    assert res.content == b"slippi-bytes"


def test_tampered_or_expired_signature_rejected(client, db_session):
    _, private_id = _seed_repos_and_files(db_session)

    exp = int(time.time()) + 60
    good_sig = create_download_signature(private_id, exp)

    tampered = client.get(f"/api/v1/replays/files/{private_id}/download?exp={exp}&sig={'0' * len(good_sig)}")
    assert tampered.status_code == 404

    expired_exp = int(time.time()) - 10
    expired_sig = create_download_signature(private_id, expired_exp)
    expired = client.get(f"/api/v1/replays/files/{private_id}/download?exp={expired_exp}&sig={expired_sig}")
    assert expired.status_code == 404

    wrong_file = client.get(f"/api/v1/replays/files/{private_id}/download?exp={exp}&sig={create_download_signature(private_id + 999, exp)}")
    assert wrong_file.status_code == 404
