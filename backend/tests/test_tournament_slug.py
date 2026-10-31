"""Tournament-name lookups must never fail an upload; they fall back to the cached name."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.core.config import settings
from app.services import tournament_slug
from app.services.tournament_slug import resolve_tournament_name

SLUG = "tournament/weekly-9"
STALE = datetime.now(timezone.utc) - timedelta(days=2)


class _FakeResponse:
    def __init__(self, body=None, status_code=200):
        self._body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=httpx.Request("POST", "http://x"), response=None)

    def json(self):
        return self._body


@pytest.fixture()
def provider(monkeypatch):
    """Route provider requests to a fake; returns the list of recorded calls."""
    monkeypatch.setattr(settings, "START_GG_TOKEN", "token")
    monkeypatch.setattr(tournament_slug, "_slug_cache", {})
    state = {"response": _FakeResponse({"data": {"tournament": {"name": "Weekly 9"}}}), "calls": []}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, url, **kwargs):
            state["calls"].append(kwargs["json"]["variables"]["slug"])
            response = state["response"]
            if isinstance(response, Exception):
                raise response
            return response

    monkeypatch.setattr(tournament_slug.httpx, "Client", _FakeClient)
    return state


def test_fresh_cached_name_skips_the_provider(provider):
    fresh = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert resolve_tournament_name("startgg", SLUG, cached_name="Old", cached_at=fresh) == ("Old", fresh)
    assert provider["calls"] == []


def test_stale_name_is_refetched_and_cached_in_process(provider):
    name, fetched_at = resolve_tournament_name("startgg", SLUG, cached_name="Old", cached_at=STALE)
    assert name == "Weekly 9" and fetched_at > STALE
    assert resolve_tournament_name("startgg", SLUG)[0] == "Weekly 9"
    assert provider["calls"] == [SLUG], "second lookup is served from the process cache"


def test_force_refresh_bypasses_both_caches(provider):
    resolve_tournament_name("startgg", SLUG)
    fresh = datetime.now(timezone.utc)
    resolve_tournament_name("startgg", SLUG, cached_name="Old", cached_at=fresh, force_refresh=True)
    assert provider["calls"] == [SLUG, SLUG]


def test_missing_token_returns_cached_values(provider, monkeypatch):
    monkeypatch.setattr(settings, "START_GG_TOKEN", "")
    assert resolve_tournament_name("startgg", SLUG, cached_name="Old", cached_at=STALE) == ("Old", STALE)
    assert provider["calls"] == []


@pytest.mark.parametrize(
    "response",
    [
        httpx.ConnectError("offline"),
        _FakeResponse(status_code=502),
        _FakeResponse({"data": {"tournament": {"name": ""}}}),
        _FakeResponse({"data": {}}),
    ],
    ids=["network-error", "http-error", "empty-name", "no-tournament-key"],
)
def test_provider_failures_fall_back_to_cached_values(provider, response):
    provider["response"] = response
    assert resolve_tournament_name("startgg", SLUG, cached_name="Old", cached_at=STALE) == ("Old", STALE)


@pytest.mark.parametrize(
    "body",
    [{"data": {"tournament": None}}, {"data": None, "errors": [{"message": "bad"}]}],
    ids=["unknown-slug", "graphql-error"],
)
def test_null_graphql_results_fall_back_to_cached_values(provider, body):
    provider["response"] = _FakeResponse(body)
    assert resolve_tournament_name("startgg", SLUG, cached_name="Old", cached_at=STALE) == ("Old", STALE)
