from datetime import datetime, timedelta, timezone

from app.api.v1 import users as users_api
from app.core.security import create_access_token
from app.models.repository import Repository
from app.models.tournament_series import TournamentSeries
from app.models.user import User
from app.services import tournament_slug


def _superuser_headers(db_session) -> dict[str, str]:
    superuser = User(username="root", email="root@example.com", hashed_password="x", role="superuser")
    db_session.add(superuser)
    db_session.commit()
    db_session.refresh(superuser)
    token = create_access_token(str(superuser.id))
    return {"Authorization": "Bearer " + token}


def test_saving_tournament_breaks_event_title_cache(client, db_session, monkeypatch):
    headers = _superuser_headers(db_session)
    repository = Repository(name="Weekly", is_public=True)
    db_session.add(repository)
    db_session.flush()
    fresh_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    tournament = TournamentSeries(
        name="Weekly",
        repository_id=repository.id,
        provider="startgg",
        slug="tournament/weekly-1",
        current_tournament_name="Weekly 1",
        current_tournament_name_fetched_at=fresh_at,
    )
    db_session.add(tournament)
    db_session.commit()
    db_session.refresh(tournament)

    tournament_slug._slug_cache[("startgg", "tournament/weekly-1")] = ("Weekly 1", fresh_at)

    calls = []

    def fake_resolve(provider, slug, *, cached_name=None, cached_at=None, force_refresh=False):
        calls.append(force_refresh)
        assert ("startgg", "tournament/weekly-1") not in tournament_slug._slug_cache
        return "Weekly 2", datetime.now(timezone.utc)

    monkeypatch.setattr(users_api, "resolve_tournament_name", fake_resolve)

    res = client.patch(f"/api/v1/users/tournaments/{tournament.id}", json={"is_public": False}, headers=headers)

    assert res.status_code == 200
    assert calls == [True]
    assert res.json()["current_tournament_name"] == "Weekly 2"
