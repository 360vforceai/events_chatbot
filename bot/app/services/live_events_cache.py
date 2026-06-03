"""In-memory caches: Rutgers getINVOLVED + tri-state Ticketmaster events."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, timedelta

from app.scrapers.getinvolved import fetch_upcoming_events, search_getinvolved_events
from app.services.tri_state_live_events import fetch_live_tri_state_events

logger = logging.getLogger("discord_bot")

_campus_events: list[dict] = []
_tri_state_events: list[dict] = []
_cache_ts: float = 0
_tri_cache_ts: float = 0


async def refresh_campus(max_results: int = 80) -> int:
    global _campus_events, _cache_ts
    events = await asyncio.to_thread(fetch_upcoming_events, max_results)
    _campus_events = events
    _cache_ts = time.time()
    logger.info("Campus live cache refreshed (%s upcoming)", len(_campus_events))
    return len(_campus_events)


async def refresh_tri_state(category: str = "all") -> int:
    global _tri_state_events, _tri_cache_ts
    events = await asyncio.to_thread(fetch_live_tri_state_events, category=category)
    _tri_state_events = events
    _tri_cache_ts = time.time()
    logger.info("Tri-state live cache refreshed (%s events)", len(_tri_state_events))
    return len(_tri_state_events)


async def refresh(max_results: int = 80) -> int:
    campus_n, tri_n = await asyncio.gather(
        refresh_campus(max_results),
        refresh_tri_state(),
    )
    return campus_n + tri_n


def get_upcoming_campus() -> list[dict]:
    return list(_campus_events)


def get_upcoming_tri_state() -> list[dict]:
    return list(_tri_state_events)


def age_minutes() -> int | None:
    if not _cache_ts:
        return None
    return int((time.time() - _cache_ts) / 60)


def tri_state_age_minutes() -> int | None:
    if not _tri_cache_ts:
        return None
    return int((time.time() - _tri_cache_ts) / 60)


def freshness_label() -> str:
    mins = age_minutes()
    if mins is None:
        return "campus: loading…"
    if mins < 1:
        return "campus: live just now"
    return f"campus: live {mins} min ago"


def tri_state_freshness_label() -> str:
    from app.config import settings

    if not (settings.ticketmaster_api_key or "").strip():
        return "tri-state: add TICKETMASTER_API_KEY in bot/.env"
    mins = tri_state_age_minutes()
    if mins is None:
        return "tri-state: loading…"
    if mins < 1:
        return "tri-state: live just now"
    return f"tri-state: live {mins} min ago"


async def search_live(keywords: str, max_results: int = 15) -> list[dict]:
    """Campus getINVOLVED search."""
    if not keywords or not keywords.strip():
        if _campus_events and age_minutes() is not None and age_minutes() < 20:
            return _campus_events[:max_results]
        return await asyncio.to_thread(fetch_upcoming_events, max_results)
    return await asyncio.to_thread(search_getinvolved_events, keywords.strip(), max_results)


async def search_tri_state_live(category: str = "all", max_results: int = 15) -> list[dict]:
    if _tri_state_events and tri_state_age_minutes() is not None and tri_state_age_minutes() < 20:
        return _tri_state_events[:max_results]
    events = await asyncio.to_thread(fetch_live_tri_state_events, category=category)
    return events[:max_results]


def campus_within_days(days: int = 7) -> list[dict]:
    filtered = _within_days(_campus_events, days)
    if filtered:
        return filtered
    # Sparse live API week — show soonest upcoming from cache instead of empty.
    return _campus_events[:10]


def tri_state_within_days(days: int = 7) -> list[dict]:
    filtered = _within_days(_tri_state_events, days)
    if filtered:
        return filtered
    return _tri_state_events[:10]


def _within_days(events: list[dict], days: int) -> list[dict]:
    cutoff = date.today()
    end = cutoff + timedelta(days=days)
    out = []
    for e in events:
        try:
            d = date.fromisoformat(e.get("date", ""))
        except ValueError:
            continue
        if cutoff <= d <= end:
            out.append(e)
    return out
