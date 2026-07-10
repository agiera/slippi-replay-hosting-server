from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings

CACHE_TTL = timedelta(hours=24)
_PROVIDER_START_GG = "startgg"
_PROVIDER_PARRY_GG = "parrygg"

# Process-local cache to avoid repeated provider requests for identical slugs.
_slug_cache: dict[tuple[str, str], tuple[str, datetime]] = {}


class TournamentSlugProviderError(ValueError):
    pass


def _normalize_provider(provider: str | None) -> str | None:
    if provider is None:
        return None
    normalized = provider.strip().lower().replace(".", "")
    if not normalized:
        return None
    if normalized not in {_PROVIDER_START_GG, _PROVIDER_PARRY_GG}:
        raise TournamentSlugProviderError("Provider must be one of: startgg, parrygg")
    return normalized


def _normalize_slug(slug: str | None) -> str | None:
    if slug is None:
        return None
    normalized = slug.strip().strip("/")
    return normalized or None


def normalize_provider_slug(provider: str | None, slug: str | None) -> tuple[str | None, str | None]:
    normalized_provider = _normalize_provider(provider)
    normalized_slug = _normalize_slug(slug)

    if bool(normalized_provider) != bool(normalized_slug):
        raise TournamentSlugProviderError("Both provider and slug are required together")

    return normalized_provider, normalized_slug


def _token_for_provider(provider: str) -> str:
    if provider == _PROVIDER_START_GG:
        return settings.START_GG_TOKEN
    if provider == _PROVIDER_PARRY_GG:
        return settings.PARRY_GG_TOKEN
    return ""


def _endpoint_for_provider(provider: str) -> str:
    if provider == _PROVIDER_START_GG:
        return "https://api.start.gg/gql/alpha"
    return "https://api.parry.gg/gql/alpha"


def _is_fresh(timestamp: datetime, *, now: datetime) -> bool:
    reference = timestamp.astimezone(timezone.utc) if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
    return now - reference < CACHE_TTL


def resolve_tournament_name(
    provider: str,
    slug: str,
    *,
    cached_name: str | None = None,
    cached_at: datetime | None = None,
    force_refresh: bool = False,
) -> tuple[str | None, datetime | None]:
    now = datetime.now(timezone.utc)

    if not force_refresh and cached_name and cached_at and _is_fresh(cached_at, now=now):
        return cached_name, cached_at

    cache_key = (provider, slug)
    if not force_refresh:
        local_cached = _slug_cache.get(cache_key)
        if local_cached and _is_fresh(local_cached[1], now=now):
            return local_cached

    token = _token_for_provider(provider)
    if not token:
        return cached_name, cached_at

    query = "query TournamentBySlug($slug: String!) { tournament(slug: $slug) { name } }"
    payload = {
        "query": query,
        "variables": {"slug": slug},
    }

    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.post(
                _endpoint_for_provider(provider),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
    except Exception:
        return cached_name, cached_at

    tournament_name = body.get("data", {}).get("tournament", {}).get("name")
    if not tournament_name:
        return cached_name, cached_at

    fetched_at = datetime.now(timezone.utc)
    _slug_cache[cache_key] = (tournament_name, fetched_at)
    return tournament_name, fetched_at
