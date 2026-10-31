"""Partial live-stream copies are replaced by more complete copies of the same game."""
import hashlib

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.file import File
from app.services.replay_identity import identify_slp
from app.services.replay_upload import DuplicateReplayError, persist_replay_upload
from app.services.view_cache import replay_artifact_paths
from tests.test_replay_dedupe import _seed_token, _stream, _upload

FOOTER = b"U\x08metadata{U\x07startAtSU\x142026-01-01T00:00:00Z}}"


def recording(seed: int, frames: int, *, finished: bool) -> tuple[bytes, bytes]:
    """Return (bytes as streamed live, bytes on disk) for a synthetic recording.

    Event Payloads declares Game Start (0x36, 4 bytes) and a frame event (0x37,
    2 bytes); the Game Start payload is the random seed.
    """
    events = bytes([0x35, 7, 0x36, 0, 4, 0x37, 0, 2]) + bytes([0x36]) + seed.to_bytes(4, "big")
    events += b"".join(bytes([0x37]) + (i % 65536).to_bytes(2, "big") for i in range(frames))
    streamed = b"{U\x03raw[$U#l\x00\x00\x00\x00" + events + (FOOTER if finished else b"")
    if not finished:
        return streamed, streamed
    on_disk = bytearray(streamed)
    on_disk[11:15] = len(events).to_bytes(4, "big")
    return streamed, bytes(on_disk)


def test_identify_slp_keys_copies_of_one_recording_together():
    _, complete = recording(1, 50, finished=True)
    partial, _ = recording(1, 10, finished=False)
    other, _ = recording(2, 50, finished=False)

    a, b, c = identify_slp(complete), identify_slp(partial), identify_slp(other)
    assert a.game_key == b.game_key != c.game_key
    assert (a.is_partial, b.is_partial) == (False, True)

    assert identify_slp(b"not a replay") is None
    assert identify_slp(partial[:20]) is None, "Game Start not received yet"
    # A frame payload that happens to contain the metadata key doesn't count.
    tricky = partial + b"U\x08metadata"
    assert identify_slp(tricky).is_partial is True


def _rows(db_session):
    db_session.expire_all()
    return db_session.scalars(select(File).order_by(File._id)).all()


def _artifacts_exist(row) -> bool:
    return any(path.exists() for path in replay_artifact_paths(row.folder, row.name))


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "REPLAY_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "REPLAY_VIEW_ARCHIVE_DIR", str(tmp_path / "archive"))
    monkeypatch.setattr(settings, "REPLAY_VIEW_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path


def test_complete_upload_replaces_a_partial_stream(client, db_session, storage):
    _seed_token(db_session, repo_name="public", raw_token="slp_partial_a")
    cut_short, _ = recording(7, 20, finished=False)
    _, finished_file = recording(7, 60, finished=True)

    first = _stream(client, "slp_partial_a", cut_short)
    assert first.status_code == 200
    [partial_row] = _rows(db_session)
    assert partial_row.is_partial is True and partial_row.game_key
    assert _artifacts_exist(partial_row)
    partial_key = partial_row.game_key
    partial_paths = replay_artifact_paths(partial_row.folder, partial_row.name)

    complete = _upload(client, "slp_partial_a", data=finished_file)
    assert complete.status_code == 200
    [complete_row] = _rows(db_session)
    assert complete_row._id == complete.json()["id"]
    assert complete_row.is_partial is False
    assert complete_row.game_key == partial_key
    assert not any(path.exists() for path in partial_paths), "replaced copy's files are removed"
    assert _artifacts_exist(complete_row)

    # A late retry of the cut-short stream is a duplicate of the complete copy.
    late = _stream(client, "slp_partial_a", cut_short)
    assert late.status_code == 409
    assert late.json()["sha256"] == hashlib.sha256(finished_file).hexdigest()
    assert len(_rows(db_session)) == 1


def test_longer_partial_replaces_shorter_and_not_the_reverse(client, db_session, storage):
    _seed_token(db_session, repo_name="public", raw_token="slp_partial_b")
    short, _ = recording(9, 10, finished=False)
    longer, _ = recording(9, 30, finished=False)

    assert _stream(client, "slp_partial_b", short).status_code == 200
    assert _stream(client, "slp_partial_b", longer).status_code == 200
    [kept] = _rows(db_session)
    assert kept.source_size_bytes == len(longer)

    again = _stream(client, "slp_partial_b", short)
    assert again.status_code == 409
    assert again.json()["id"] == kept._id


def test_complete_copies_and_other_games_are_never_replaced(client, db_session, storage):
    _seed_token(db_session, repo_name="public", raw_token="slp_partial_c")
    _, game_a = recording(11, 40, finished=True)
    _, game_a_other_copy = recording(11, 41, finished=True)
    partial_b, _ = recording(12, 10, finished=False)

    for data in (game_a, game_a_other_copy):
        assert _upload(client, "slp_partial_c", data=data).status_code == 200
    assert _stream(client, "slp_partial_c", partial_b).status_code == 200
    assert len(_rows(db_session)) == 3


def test_replaced_files_survive_a_rolled_back_transaction(db_session, storage):
    token, _repo = _seed_token(db_session, repo_name="public", raw_token="slp_partial_d")
    partial, _ = recording(13, 10, finished=False)
    _, complete = recording(13, 30, finished=True)

    persist_replay_upload(db_session, token_row=token, repository_name="public", original_name="g.slp", data=partial)
    db_session.commit()
    [partial_row] = _rows(db_session)

    persist_replay_upload(db_session, token_row=token, repository_name="public", original_name="g.slp", data=complete)
    db_session.rollback()

    [still_there] = _rows(db_session)
    assert still_there._id == partial_row._id
    assert _artifacts_exist(still_there)


def test_partial_without_game_start_is_stored_but_not_grouped(db_session, storage):
    token, _repo = _seed_token(db_session, repo_name="public", raw_token="slp_partial_e")
    tiny = b"{U\x03raw[$U#l\x00\x00\x00\x00\x35"
    persist_replay_upload(db_session, token_row=token, repository_name="public", original_name="g.slp", data=tiny)
    db_session.commit()
    [row] = _rows(db_session)
    assert (row.game_key, row.is_partial, row.source_size_bytes) == (None, None, len(tiny))
    with pytest.raises(DuplicateReplayError):
        persist_replay_upload(db_session, token_row=token, repository_name="public", original_name="g.slp", data=tiny)


def _fake_parser(*, ports: tuple[int, ...]):
    from app.services.peppi_ingest import ParsedReplayData

    def parse(data: bytes, suffix: str = ".slp") -> ParsedReplayData:
        players = [
            {"port": port, "type": 0, "character_id": 2, "connect_code": None, "display_name": None,
             "tag": f"p{port}", "user_id": None}
            for port in ports
        ]
        return ParsedReplayData(
            stage=31, start_time="2026-01-01T00:00:00Z", last_frame=len(data), is_teams=0,
            players=players, peppi_bytes=b"peppi:" + data,
        )

    return parse


def test_replacing_a_partial_also_removes_its_game_and_players(db_session, storage):
    from app.models.game import Game
    from app.models.player import Player

    token, _repo = _seed_token(db_session, repo_name="public", raw_token="slp_partial_f")
    partial, _ = recording(14, 10, finished=False)
    _, complete = recording(14, 30, finished=True)

    persist_replay_upload(
        db_session, token_row=token, repository_name="public", original_name="g.slp",
        data=partial, parse_replay=_fake_parser(ports=(1, 2)),
    )
    db_session.commit()
    [partial_row] = _rows(db_session)
    assert partial_row.name.endswith(".peppi.json.gz")
    assert _artifacts_exist(partial_row)
    partial_paths = replay_artifact_paths(partial_row.folder, partial_row.name)

    new_row = persist_replay_upload(
        db_session, token_row=token, repository_name="public", original_name="g.slp",
        data=complete, parse_replay=_fake_parser(ports=(1, 3)),
    )
    db_session.commit()

    [game] = db_session.scalars(select(Game)).all()
    assert game.file_id == new_row._id and game.last_frame == len(complete)
    assert sorted(p.port for p in db_session.scalars(select(Player))) == [1, 3]
    assert not any(path.exists() for path in partial_paths)


def test_stream_cut_off_inside_the_footer_is_stored_as_a_partial(client, db_session, storage):
    _seed_token(db_session, repo_name="public", raw_token="slp_partial_g")
    finished, finished_on_disk = recording(15, 20, finished=True)
    cut = finished[: len(finished) - len(FOOTER) + 14]

    res = _stream(client, "slp_partial_g", cut)
    assert res.status_code == 200
    [row] = _rows(db_session)
    assert row.is_partial is True

    assert _upload(client, "slp_partial_g", data=finished_on_disk).status_code == 200
    [row] = _rows(db_session)
    assert row.is_partial is False
