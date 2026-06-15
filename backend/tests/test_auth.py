import hashlib
from pathlib import Path

from app.core.security import create_access_token
from app.core.config import settings
from app.models.api_token import ApiToken
from app.models.file import File
from app.models.game import Game
from app.models.player import Player
from app.models.repository import Repository
from app.models.user import User
from app.services.peppi_ingest import ParsedReplayData
from sqlalchemy import select


def test_signup_and_me(client):
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    assert signup_res.status_code == 200
    body = signup_res.json()
    assert body["access_token"]
    assert body["refresh_token"]

    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me_res.status_code == 200
    me_body = me_res.json()
    assert me_body["username"] == "alice"


def test_refresh_rotates_tokens(client):
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={"username": "bob", "email": "bob@example.com", "password": "password123"},
    )
    assert signup_res.status_code == 200
    first_pair = signup_res.json()

    refresh_res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_pair["refresh_token"]},
    )
    assert refresh_res.status_code == 200
    second_pair = refresh_res.json()
    assert second_pair["access_token"] != first_pair["access_token"]
    assert second_pair["refresh_token"] != first_pair["refresh_token"]

    reuse_old_res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_pair["refresh_token"]},
    )
    assert reuse_old_res.status_code == 401


def test_logout_revokes_refresh_token(client):
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={"username": "carol", "email": "carol@example.com", "password": "password123"},
    )
    assert signup_res.status_code == 200
    pair = signup_res.json()

    logout_res = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": pair["refresh_token"]},
    )
    assert logout_res.status_code == 200

    refresh_res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": pair["refresh_token"]},
    )
    assert refresh_res.status_code == 401


def test_public_files_endpoint_is_accessible_without_auth(client):
    files_res = client.get("/api/v1/replays/files")
    assert files_res.status_code == 200
    payload = files_res.json()
    assert "items" in payload
    assert "next_cursor" in payload
    assert isinstance(payload["items"], list)


def test_public_files_endpoint_supports_filters_and_pagination(client, db_session):
    file_one = File(folder="ranked/set1", name="one.slp", size_bytes=123, birth_time="2024-01-01")
    file_two = File(folder="casual/friendlies", name="two.slp", size_bytes=456, birth_time="2024-02-01")
    db_session.add_all([file_one, file_two])
    db_session.flush()

    game_one = Game(file_id=file_one._id, is_ranked=1, is_teams=0, start_time="2024-01-01T12:00:00Z")
    game_two = Game(file_id=file_two._id, is_ranked=0, is_teams=0, start_time="2024-02-01T12:00:00Z")
    db_session.add_all([game_one, game_two])
    db_session.flush()

    player_one = Player(game_id=game_one._id, port=1, character_id=2, display_name="Mango")
    player_two = Player(game_id=game_two._id, port=1, character_id=18, display_name="Zain")
    db_session.add_all([player_one, player_two])
    db_session.commit()

    page_res = client.get("/api/v1/replays/files", params={"limit": 1})
    assert page_res.status_code == 200
    page_body = page_res.json()
    assert len(page_body["items"]) == 1
    assert page_body["next_cursor"] is not None

    keyword_res = client.get("/api/v1/replays/files", params={"keyword": "ranked"})
    assert keyword_res.status_code == 200
    keyword_items = keyword_res.json()["items"]
    assert len(keyword_items) == 1
    assert keyword_items[0]["name"] == "one.slp"
    assert keyword_items[0]["player_1"] == "Mango"
    assert keyword_items[0]["player_2"] is None
    assert keyword_items[0]["stage"] is None
    assert keyword_items[0]["game_duration"] is None
    assert keyword_items[0]["datetime_played"] == "2024-01-01T12:00:00Z"

    ranked_res = client.get("/api/v1/replays/files", params={"ranked": 1})
    assert ranked_res.status_code == 200
    ranked_items = ranked_res.json()["items"]
    assert len(ranked_items) == 1
    assert ranked_items[0]["name"] == "one.slp"

    player_res = client.get("/api/v1/replays/files", params={"player": "zain"})
    assert player_res.status_code == 200
    player_items = player_res.json()["items"]
    assert len(player_items) == 1
    assert player_items[0]["name"] == "two.slp"


def test_public_files_endpoint_supports_repository_and_collection_filters(client, db_session):
    file_alpha = File(folder="uploads/alpha/ladder/2024/01/01", name="a.slp", size_bytes=1, birth_time="2024-01-01")
    file_beta = File(folder="uploads/beta/weeklies/2024/01/01", name="b.slp", size_bytes=1, birth_time="2024-01-01")
    file_public = File(folder="public/locals", name="c.slp", size_bytes=1, birth_time="2024-01-01")
    db_session.add_all([file_alpha, file_beta, file_public])
    db_session.commit()

    repo_res = client.get("/api/v1/replays/files", params={"repository": "alpha,beta"})
    assert repo_res.status_code == 200
    repo_names = {item["name"] for item in repo_res.json()["items"]}
    assert repo_names == {"a.slp", "b.slp"}

    collection_res = client.get("/api/v1/replays/files", params={"collection": "ladder,locals"})
    assert collection_res.status_code == 200
    collection_names = {item["name"] for item in collection_res.json()["items"]}
    assert collection_names == {"a.slp", "c.slp"}

    both_res = client.get(
        "/api/v1/replays/files",
        params={"repository": "alpha,beta", "collection": "ladder"},
    )
    assert both_res.status_code == 200
    both_names = {item["name"] for item in both_res.json()["items"]}
    assert both_names == {"a.slp"}


def test_public_replay_filter_options_endpoint(client, db_session):
    uploader = User(
        username="filtertokens",
        email="filtertokens@example.com",
        hashed_password="x",
        role="uploader",
    )
    db_session.add(uploader)
    db_session.flush()

    db_session.add_all(
        [
            ApiToken(
                user_id=uploader.id,
                collection_name="ladder",
                token_prefix="tok_lad",
                token_hash=hashlib.sha256(b"filter-token-ladder").hexdigest(),
            ),
            ApiToken(
                user_id=uploader.id,
                collection_name="weeklies",
                token_prefix="tok_wk",
                token_hash=hashlib.sha256(b"filter-token-weeklies").hexdigest(),
            ),
            File(folder="uploads/alpha/2026/06/14", name="a.slp", size_bytes=1, birth_time="2024-01-01"),
            File(folder="uploads/beta/weeklies/2024/01/01", name="b.slp", size_bytes=1, birth_time="2024-01-01"),
            File(folder="public/locals", name="c.slp", size_bytes=1, birth_time="2024-01-01"),
        ]
    )
    db_session.commit()

    res = client.get("/api/v1/replays/filters")
    assert res.status_code == 200
    body = res.json()
    assert body["repositories"] == ["alpha", "beta", "public"]
    assert body["collections"] == ["ladder", "locals", "weeklies"]


def test_public_files_endpoint_enriches_player_rank_rating(client, db_session, monkeypatch):
    file_row = File(folder="ranked/set2", name="ranked.slp", size_bytes=321, birth_time="2024-03-01")
    db_session.add(file_row)
    db_session.flush()

    game_row = Game(
        file_id=file_row._id,
        is_ranked=1,
        is_teams=0,
        start_time="2024-03-01T12:00:00Z",
        last_frame=7200,
        stage=31,
    )
    db_session.add(game_row)
    db_session.flush()

    db_session.add_all(
        [
            Player(
                game_id=game_row._id,
                port=1,
                character_id=2,
                character_color=0,
                display_name="Mango",
                connect_code="MANGO#001",
                is_winner=1,
            ),
            Player(
                game_id=game_row._id,
                port=2,
                character_id=18,
                character_color=1,
                display_name="Zain",
                connect_code="ZAIN#001",
                is_winner=0,
            ),
        ]
    )
    db_session.commit()

    class _FakeProfile:
        def __init__(self, rank, rating):
            self.rank = rank
            self.rating = rating

    def _fake_lookup(code):
        if code == "MANGO#001":
            return _FakeProfile("Diamond_I", 2004)
        if code == "ZAIN#001":
            return _FakeProfile("Master_II", 2301)
        return None

    monkeypatch.setattr("app.api.v1.replays.fetch_profile_by_connect_code", _fake_lookup)

    res = client.get("/api/v1/replays/files", params={"keyword": "ranked"})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    item = items[0]

    assert item["player_1_info"]["connect_code"] == "MANGO#001"
    assert item["player_1_info"]["rank"] == "Diamond_I"
    assert item["player_1_info"]["rating"] == 2004
    assert item["player_1_info"]["is_winner"] == 1

    assert item["player_2_info"]["connect_code"] == "ZAIN#001"
    assert item["player_2_info"]["rank"] == "Master_II"
    assert item["player_2_info"]["rating"] == 2301
    assert item["player_2_info"]["is_winner"] == 0


def test_public_files_keyword_and_multi_character_filters_are_game_wide(client, db_session):
    file_both = File(folder="ranked/set3", name="both.slp", size_bytes=100, birth_time="2024-04-01")
    file_marth = File(folder="ranked/set3", name="marth.slp", size_bytes=100, birth_time="2024-04-01")
    file_pika = File(folder="ranked/set3", name="pika.slp", size_bytes=100, birth_time="2024-04-01")
    db_session.add_all([file_both, file_marth, file_pika])
    db_session.flush()

    game_both = Game(file_id=file_both._id, is_ranked=1, is_teams=0, start_time="2024-04-01T12:00:00Z")
    game_marth = Game(file_id=file_marth._id, is_ranked=1, is_teams=0, start_time="2024-04-01T12:05:00Z")
    game_pika = Game(file_id=file_pika._id, is_ranked=1, is_teams=0, start_time="2024-04-01T12:10:00Z")
    db_session.add_all([game_both, game_marth, game_pika])
    db_session.flush()

    db_session.add_all(
        [
            Player(game_id=game_both._id, port=1, character_id=9, display_name="PlayerA"),
            Player(game_id=game_both._id, port=2, character_id=13, display_name="PlayerB"),
            Player(game_id=game_marth._id, port=1, character_id=9, display_name="PlayerC"),
            Player(game_id=game_pika._id, port=1, character_id=13, display_name="PlayerD"),
        ]
    )
    db_session.commit()

    keyword_res = client.get("/api/v1/replays/files", params={"keyword": "marth pika"})
    assert keyword_res.status_code == 200
    keyword_names = {item["name"] for item in keyword_res.json()["items"]}
    assert keyword_names == {"both.slp"}

    character_res = client.get("/api/v1/replays/files", params={"character": "9,13"})
    assert character_res.status_code == 200
    character_names = {item["name"] for item in character_res.json()["items"]}
    assert character_names == {"both.slp"}


def test_public_files_rank_filter_supports_single_or_two_rank_assignments(client, db_session, monkeypatch):
    file_match = File(folder="ranked/set4", name="match.slp", size_bytes=100, birth_time="2024-05-01")
    file_mismatch = File(folder="ranked/set4", name="mismatch.slp", size_bytes=100, birth_time="2024-05-01")
    db_session.add_all([file_match, file_mismatch])
    db_session.flush()

    game_match = Game(file_id=file_match._id, is_ranked=1, is_teams=0, start_time="2024-05-01T12:00:00Z")
    game_mismatch = Game(file_id=file_mismatch._id, is_ranked=1, is_teams=0, start_time="2024-05-01T12:05:00Z")
    db_session.add_all([game_match, game_mismatch])
    db_session.flush()

    db_session.add_all(
        [
            Player(game_id=game_match._id, port=1, character_id=2, display_name="A", connect_code="A#1"),
            Player(game_id=game_match._id, port=2, character_id=9, display_name="B", connect_code="B#1"),
            Player(game_id=game_mismatch._id, port=1, character_id=2, display_name="C", connect_code="C#1"),
            Player(game_id=game_mismatch._id, port=2, character_id=9, display_name="D", connect_code="D#1"),
        ]
    )
    db_session.commit()

    class _FakeProfile:
        def __init__(self, rank, rating):
            self.rank = rank
            self.rating = rating

    def _fake_lookup(code):
        mapping = {
            "A#1": _FakeProfile("Diamond_I", 2000),
            "B#1": _FakeProfile("Master_II", 2200),
            "C#1": _FakeProfile("Diamond_I", 2001),
            "D#1": _FakeProfile("Gold_I", 1700),
        }
        return mapping.get(code)

    monkeypatch.setattr("app.api.v1.replays.fetch_profile_by_connect_code", _fake_lookup)

    one_rank = client.get("/api/v1/replays/files", params={"rank": "Diamond_I"})
    assert one_rank.status_code == 200
    one_rank_names = {item["name"] for item in one_rank.json()["items"]}
    assert one_rank_names == {"match.slp", "mismatch.slp"}

    two_rank = client.get("/api/v1/replays/files", params={"rank": "Diamond_I,Master_II"})
    assert two_rank.status_code == 200
    two_rank_names = {item["name"] for item in two_rank.json()["items"]}
    assert two_rank_names == {"match.slp"}

    reverse_two_rank = client.get("/api/v1/replays/files", params={"rank": "Master_II,Diamond_I"})
    assert reverse_two_rank.status_code == 200
    reverse_names = {item["name"] for item in reverse_two_rank.json()["items"]}
    assert reverse_names == {"match.slp"}


def test_public_files_numeric_rank_bounds_require_both_player_ratings(client, db_session, monkeypatch):
    file_in = File(folder="ranked/set5", name="in.slp", size_bytes=100, birth_time="2024-06-01")
    file_out = File(folder="ranked/set5", name="out.slp", size_bytes=100, birth_time="2024-06-01")
    file_missing = File(folder="ranked/set5", name="missing.slp", size_bytes=100, birth_time="2024-06-01")
    db_session.add_all([file_in, file_out, file_missing])
    db_session.flush()

    game_in = Game(file_id=file_in._id, is_ranked=1, is_teams=0, start_time="2024-06-01T12:00:00Z")
    game_out = Game(file_id=file_out._id, is_ranked=1, is_teams=0, start_time="2024-06-01T12:05:00Z")
    game_missing = Game(file_id=file_missing._id, is_ranked=1, is_teams=0, start_time="2024-06-01T12:10:00Z")
    db_session.add_all([game_in, game_out, game_missing])
    db_session.flush()

    db_session.add_all(
        [
            Player(game_id=game_in._id, port=1, character_id=2, display_name="A", connect_code="A#2"),
            Player(game_id=game_in._id, port=2, character_id=9, display_name="B", connect_code="B#2"),
            Player(game_id=game_out._id, port=1, character_id=2, display_name="C", connect_code="C#2"),
            Player(game_id=game_out._id, port=2, character_id=9, display_name="D", connect_code="D#2"),
            Player(game_id=game_missing._id, port=1, character_id=2, display_name="E", connect_code="E#2"),
            Player(game_id=game_missing._id, port=2, character_id=9, display_name="F", connect_code="F#2"),
        ]
    )
    db_session.commit()

    class _FakeProfile:
        def __init__(self, rank, rating):
            self.rank = rank
            self.rating = rating

    def _fake_lookup(code):
        mapping = {
            "A#2": _FakeProfile("Diamond_I", 1900),
            "B#2": _FakeProfile("Master_II", 2000),
            "C#2": _FakeProfile("Diamond_I", 1700),
            "D#2": _FakeProfile("Master_II", 2000),
            "E#2": None,
            "F#2": _FakeProfile("Master_II", 2000),
        }
        return mapping.get(code)

    monkeypatch.setattr("app.api.v1.replays.fetch_profile_by_connect_code", _fake_lookup)

    res = client.get("/api/v1/replays/files", params={"min_rank": 1800, "max_rank": 2100})
    assert res.status_code == 200
    names = {item["name"] for item in res.json()["items"]}
    assert names == {"in.slp"}


def test_api_token_generation_requires_uploader_or_superuser(client, db_session):
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={"username": "tokenuser", "email": "tokenuser@example.com", "password": "password123"},
    )
    assert signup_res.status_code == 200
    access_token = signup_res.json()["access_token"]

    deny_res = client.post(
        "/api/v1/users/me/api-tokens",
        json={"collection_name": "uploader-token"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert deny_res.status_code == 403

    user = db_session.scalar(select(User).where(User.username == "tokenuser"))
    assert user is not None
    user.role = "uploader"
    db_session.add(user)
    db_session.commit()

    allow_res = client.post(
        "/api/v1/users/me/api-tokens",
        json={"collection_name": "uploader-token"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert allow_res.status_code == 200
    body = allow_res.json()
    assert body["token"].startswith("slp_")
    assert body["token_info"]["collection_name"] == "uploader-token"


def test_superuser_can_update_other_user_roles(client, db_session):
    normal_signup = client.post(
        "/api/v1/auth/signup",
        json={"username": "normaluser", "email": "normal@example.com", "password": "password123"},
    )
    assert normal_signup.status_code == 200

    superuser = User(
        username="root",
        email="root@example.com",
        hashed_password="x",
        role="superuser",
    )
    db_session.add(superuser)
    db_session.commit()
    db_session.refresh(superuser)

    super_access_token = create_access_token(str(superuser.id))

    users_res = client.get("/api/v1/users", headers={"Authorization": f"Bearer {super_access_token}"})
    assert users_res.status_code == 200
    users = users_res.json()
    normal_user = next((u for u in users if u["username"] == "normaluser"), None)
    assert normal_user is not None

    role_update_res = client.patch(
        f"/api/v1/users/{normal_user['id']}/role",
        json={"role": "uploader"},
        headers={"Authorization": f"Bearer {super_access_token}"},
    )
    assert role_update_res.status_code == 200
    assert role_update_res.json()["role"] == "uploader"


def test_upload_endpoint_accepts_api_token_and_persists_file(client, db_session, tmp_path):
    public_repo = Repository(name="public", is_public=True)
    db_session.add(public_repo)
    db_session.commit()
    db_session.refresh(public_repo)

    uploader = User(
        username="uploaduser",
        email="uploaduser@example.com",
        hashed_password="x",
        role="uploader",
    )
    uploader.repositories.append(public_repo)
    db_session.add(uploader)
    db_session.commit()
    db_session.refresh(uploader)

    raw_token = "slp_test_upload_token"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    token_row = ApiToken(
        user_id=uploader.id,
        collection_name="test-token",
        token_prefix=raw_token[:12],
        token_hash=token_hash,
    )
    token_row.repositories.append(public_repo)
    db_session.add(token_row)
    db_session.commit()

    original_storage_dir = settings.REPLAY_STORAGE_DIR
    settings.REPLAY_STORAGE_DIR = str(tmp_path)
    try:
        upload_res = client.post(
            "/api/v1/uploads/files",
            data={"repository": "public"},
            files={"file": ("sample.slp", b"SLP-DATA", "application/octet-stream")},
            headers={"X-API-Token": raw_token},
        )
    finally:
        settings.REPLAY_STORAGE_DIR = original_storage_dir

    assert upload_res.status_code == 200
    payload = upload_res.json()
    assert payload["name"].endswith(".slp")
    assert payload["size_bytes"] == 8

    stored = db_session.scalar(select(File).where(File._id == payload["id"]))
    assert stored is not None
    assert "/test-token/" in stored.folder
    saved_path = Path(tmp_path) / stored.folder / stored.name
    assert saved_path.exists()


def _seed_uploader_with_public_repo(db_session):
    public_repo = Repository(name="public", is_public=True)
    db_session.add(public_repo)
    db_session.commit()
    db_session.refresh(public_repo)

    uploader = User(
        username="uploadparseuser",
        email="uploadparseuser@example.com",
        hashed_password="x",
        role="uploader",
    )
    uploader.repositories.append(public_repo)
    db_session.add(uploader)
    db_session.commit()
    db_session.refresh(uploader)

    raw_token = "slp_test_upload_parse_token"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    token_row = ApiToken(
        user_id=uploader.id,
        collection_name="test-parse-token",
        token_prefix=raw_token[:12],
        token_hash=token_hash,
    )
    token_row.repositories.append(public_repo)
    db_session.add(token_row)
    db_session.commit()

    return raw_token


def test_upload_endpoint_parses_metadata_and_persists_game_rows(client, db_session, tmp_path, monkeypatch):
    raw_token = _seed_uploader_with_public_repo(db_session)

    fake_parsed = ParsedReplayData(
        stage=3,
        start_time="2024-03-02T18:20:00Z",
        last_frame=9000,
        is_teams=0,
        players=[
            {
                "port": 1,
                "type": 0,
                "character_id": 2,
                "connect_code": "MANGO#001",
                "display_name": "Mango",
                "tag": "Mang0",
                "user_id": "uid-mango",
            },
            {
                "port": 2,
                "type": 0,
                "character_id": 18,
                "connect_code": "ZAIN#001",
                "display_name": "Zain",
                "tag": "Zain",
                "user_id": "uid-zain",
            },
        ],
        peppi_bytes=b"COMPRESSED-PEPPI",
    )
    monkeypatch.setattr("app.api.v1.uploads.parse_slippi_bytes", lambda *_args, **_kwargs: fake_parsed)

    original_storage_dir = settings.REPLAY_STORAGE_DIR
    settings.REPLAY_STORAGE_DIR = str(tmp_path)
    try:
        upload_res = client.post(
            "/api/v1/uploads/files",
            data={"repository": "public"},
            files={"file": ("parsed.slp", b"SLP-DATA", "application/octet-stream")},
            headers={"X-API-Token": raw_token},
        )
    finally:
        settings.REPLAY_STORAGE_DIR = original_storage_dir

    assert upload_res.status_code == 200
    payload = upload_res.json()
    assert payload["name"].endswith(".peppi.json.gz")
    assert payload["size_bytes"] == len(fake_parsed.peppi_bytes)

    stored = db_session.scalar(select(File).where(File._id == payload["id"]))
    assert stored is not None
    game = db_session.scalar(select(Game).where(Game.file_id == stored._id))
    assert game is not None
    assert game.stage == 3
    assert game.last_frame == 9000
    assert game.start_time == "2024-03-02T18:20:00Z"

    players = db_session.scalars(select(Player).where(Player.game_id == game._id).order_by(Player.port)).all()
    assert len(players) == 2
    assert players[0].display_name == "Mango"
    assert players[1].display_name == "Zain"

    list_res = client.get("/api/v1/replays/files")
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    item = next((it for it in items if it["name"] == stored.name), None)
    assert item is not None
    assert item["player_1"] == "Mango"
    assert item["player_2"] == "Zain"
    assert item["stage"] == 3
    assert item["game_duration"] == 150
    assert item["datetime_played"] == "2024-03-02T18:20:00Z"


def test_upload_endpoint_falls_back_when_peppi_parse_fails(client, db_session, tmp_path, monkeypatch):
    raw_token = _seed_uploader_with_public_repo(db_session)

    def _raise_parse(*_args, **_kwargs):
        raise ValueError("bad replay")

    monkeypatch.setattr("app.api.v1.uploads.parse_slippi_bytes", _raise_parse)

    original_storage_dir = settings.REPLAY_STORAGE_DIR
    settings.REPLAY_STORAGE_DIR = str(tmp_path)
    try:
        upload_res = client.post(
            "/api/v1/uploads/files",
            data={"repository": "public"},
            files={"file": ("fallback.slp", b"SLP-DATA", "application/octet-stream")},
            headers={"X-API-Token": raw_token},
        )
    finally:
        settings.REPLAY_STORAGE_DIR = original_storage_dir

    assert upload_res.status_code == 200
    payload = upload_res.json()
    assert payload["name"].endswith(".slp")

    stored = db_session.scalar(select(File).where(File._id == payload["id"]))
    assert stored is not None
    game = db_session.scalar(select(Game).where(Game.file_id == stored._id))
    assert game is None


def test_superuser_can_create_repository_and_assign_user_membership(client, db_session):
    superuser = User(
        username="repoadmin",
        email="repoadmin@example.com",
        hashed_password="x",
        role="superuser",
    )
    db_session.add(superuser)
    db_session.commit()
    db_session.refresh(superuser)

    super_access_token = create_access_token(str(superuser.id))

    create_repo_res = client.post(
        "/api/v1/users/repositories",
        json={"name": "team-a"},
        headers={"Authorization": f"Bearer {super_access_token}"},
    )
    assert create_repo_res.status_code == 200
    created_repo = create_repo_res.json()

    signup_res = client.post(
        "/api/v1/auth/signup",
        json={"username": "member1", "email": "member1@example.com", "password": "password123"},
    )
    assert signup_res.status_code == 200
    member_id = signup_res.json()["user"]["id"]

    repositories_res = client.get(
        "/api/v1/users/repositories",
        headers={"Authorization": f"Bearer {super_access_token}"},
    )
    assert repositories_res.status_code == 200
    repository_ids = [repo["id"] for repo in repositories_res.json()]
    assert created_repo["id"] in repository_ids

    assign_res = client.put(
        f"/api/v1/users/{member_id}/repositories",
        json={"repository_ids": [created_repo["id"]]},
        headers={"Authorization": f"Bearer {super_access_token}"},
    )
    assert assign_res.status_code == 200
    assigned_names = {repo["name"] for repo in assign_res.json()["repositories"]}
    assert "public" in assigned_names
    assert "team-a" in assigned_names


def test_upload_rejects_repository_outside_api_token_scope(client, db_session, tmp_path):
    public_repo = Repository(name="public", is_public=True)
    private_repo = Repository(name="private-team", is_public=False)
    db_session.add_all([public_repo, private_repo])
    db_session.commit()
    db_session.refresh(public_repo)
    db_session.refresh(private_repo)

    uploader = User(
        username="scopeduser",
        email="scopeduser@example.com",
        hashed_password="x",
        role="uploader",
    )
    uploader.repositories.extend([public_repo, private_repo])
    db_session.add(uploader)
    db_session.commit()
    db_session.refresh(uploader)

    raw_token = "slp_scope_token"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    token_row = ApiToken(
        user_id=uploader.id,
        collection_name="public-token",
        token_prefix=raw_token[:12],
        token_hash=token_hash,
    )
    token_row.repositories.append(public_repo)
    db_session.add(token_row)
    db_session.commit()

    original_storage_dir = settings.REPLAY_STORAGE_DIR
    settings.REPLAY_STORAGE_DIR = str(tmp_path)
    try:
        upload_res = client.post(
            "/api/v1/uploads/files",
            data={"repository": "private-team"},
            files={"file": ("sample.slp", b"SLP-DATA", "application/octet-stream")},
            headers={"X-API-Token": raw_token},
        )
    finally:
        settings.REPLAY_STORAGE_DIR = original_storage_dir

    assert upload_res.status_code == 403


def test_collection_name_must_be_globally_unique(client, db_session):
    first_signup = client.post(
        "/api/v1/auth/signup",
        json={"username": "firstuser", "email": "firstuser@example.com", "password": "password123"},
    )
    assert first_signup.status_code == 200
    first_token = first_signup.json()["access_token"]

    second_signup = client.post(
        "/api/v1/auth/signup",
        json={"username": "seconduser", "email": "seconduser@example.com", "password": "password123"},
    )
    assert second_signup.status_code == 200
    second_token = second_signup.json()["access_token"]

    first_user = db_session.scalar(select(User).where(User.username == "firstuser"))
    second_user = db_session.scalar(select(User).where(User.username == "seconduser"))
    assert first_user is not None
    assert second_user is not None

    first_user.role = "uploader"
    second_user.role = "uploader"
    db_session.add(first_user)
    db_session.add(second_user)
    db_session.commit()

    first_create = client.post(
        "/api/v1/users/me/api-tokens",
        json={"collection_name": "shared-collection"},
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert first_create.status_code == 200

    second_create = client.post(
        "/api/v1/users/me/api-tokens",
        json={"collection_name": "shared-collection"},
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert second_create.status_code == 400
    assert "globally unique" in second_create.json()["detail"]
