from app.services import slippi_profile


def _clear_profile_cache():
    with slippi_profile._cache_lock:
        slippi_profile._cache.clear()


def test_fetch_profile_returns_rating_and_rank(monkeypatch):
    _clear_profile_cache()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "getUser": {
                        "rankedNetplayProfile": {
                            "ratingOrdinal": 2003.92,
                            "ratingUpdateCount": 10,
                            "dailyGlobalPlacement": None,
                            "dailyRegionalPlacement": None,
                        }
                    }
                }
            }

    monkeypatch.setattr(slippi_profile.httpx, "post", lambda *args, **kwargs: FakeResponse())

    result = slippi_profile.fetch_profile_by_connect_code("zaub\uff03866")  # full-width hash as stored by peppi

    assert result is not None
    assert result.rating == 2004
    assert result.rank == "Diamond_I"


def test_failed_lookup_is_not_cached(monkeypatch):
    _clear_profile_cache()

    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        raise RuntimeError("temporary failure")

    monkeypatch.setattr(slippi_profile.httpx, "post", fake_post)

    first = slippi_profile.fetch_profile_by_connect_code("test#999")
    second = slippi_profile.fetch_profile_by_connect_code("test#999")

    assert first is None
    assert second is None
    assert calls["count"] == 2
