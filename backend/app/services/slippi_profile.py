from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import httpx

SLIPPI_GRAPHQL_ENDPOINT = "https://internal.slippi.gg/graphql"
CACHE_TTL_SECONDS = 60 * 30

PROFILE_QUERY = """
fragment profileFields on NetplayProfile {
  ratingOrdinal
  ratingUpdateCount
  dailyGlobalPlacement
  dailyRegionalPlacement
}

query UserProfilePageQuery($cc: String, $uid: String) {
  getUser(fbUid: $uid, connectCode: $cc) {
    rankedNetplayProfile {
      ...profileFields
    }
  }
}
"""


@dataclass
class SlippiProfile:
    rank: str | None
    rating: int | None


_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, SlippiProfile | None]] = {}


def fetch_profile_by_connect_code(connect_code: str) -> SlippiProfile | None:
    # Normalize full-width hash (U+FF03 ＃) stored by peppi to standard ASCII hash.
    normalized_code = (connect_code or "").strip().replace("\uff03", "#").upper()
    if not normalized_code or "#" not in normalized_code:
        return None

    with _cache_lock:
        cached = _cache.get(normalized_code)
        if cached and cached[0] > time.time():
            return cached[1]

    profile = _fetch_profile_from_slippi(normalized_code)

    # Avoid caching failures so transient network issues do not hide ratings.
    if profile is not None:
        with _cache_lock:
            _cache[normalized_code] = (time.time() + CACHE_TTL_SECONDS, profile)

    return profile


def _fetch_profile_from_slippi(connect_code: str) -> SlippiProfile | None:
    payload = {
        "operationName": "UserProfilePageQuery",
        "variables": {"cc": connect_code, "uid": connect_code},
        "query": PROFILE_QUERY,
    }

    try:
        response = httpx.post(
            SLIPPI_GRAPHQL_ENDPOINT,
            json=payload,
            headers={"content-type": "application/json"},
            timeout=8.0,
        )
        response.raise_for_status()
        body = response.json()
    except Exception:
        return None

    profile = ((body.get("data") or {}).get("getUser") or {}).get("rankedNetplayProfile") or {}
    if not profile:
        return None

    rating = profile.get("ratingOrdinal")
    sets_played = profile.get("ratingUpdateCount") or 0
    has_placement = bool(profile.get("dailyGlobalPlacement") or profile.get("dailyRegionalPlacement"))

    rating_value = int(round(float(rating))) if rating is not None else None
    rank = _calculate_rank(rating or 0.0, has_placement, int(sets_played))

    return SlippiProfile(rank=rank, rating=rating_value)


def _calculate_rank(rating: float, has_placement: bool, sets_played: int) -> str:
    if sets_played == 0:
        return "Unranked1"
    if sets_played < 5:
        return "Unranked3"

    if rating >= 2191.75 and has_placement:
        return "Grand_Master"
    if rating >= 2350:
        return "Master_III"
    if rating >= 2275:
        return "Master_II"
    if rating >= 2191.75:
        return "Master_I"
    if rating >= 2136.28:
        return "Diamond_III"
    if rating >= 2073.67:
        return "Diamond_II"
    if rating >= 2003.92:
        return "Diamond_I"
    if rating >= 1927.03:
        return "Platinum_III"
    if rating >= 1843.0:
        return "Platinum_II"
    if rating >= 1751.83:
        return "Platinum_I"
    if rating >= 1653.52:
        return "Gold_III"
    if rating >= 1548.07:
        return "Gold_II"
    if rating >= 1435.48:
        return "Gold_I"
    if rating >= 1315.75:
        return "Silver_III"
    if rating >= 1188.88:
        return "Silver_II"
    if rating >= 1054.87:
        return "Silver_I"
    if rating >= 913.72:
        return "Bronze_III"
    if rating >= 765.43:
        return "Bronze_II"
    return "Bronze_I"
