"""In-memory cache of upcoming getINVOLVED events for real-time Discord replies."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, timedelta

from app.scrapers.getinvolved import fetch_upcoming_events, search_getinvolved_events

logger = logging.getLogger("discord_bot")

_events: list[dict] = []
_cache_ts: float = 0


async def refresh(max_results: int = 80) -> int:
    global _events, _cache_ts
    events = await asyncio.to_thread(fetch_upcoming_events, max_results)
    _events = events
    _cache_ts = time.time()
    logger.info("Live events cache refreshed (%s upcoming)", len(_events))
    return len(_events)


def get_upcoming() -> list[dict]:
    return list(_events)


def age_minutes() -> int | None:
    if not _cache_ts:
        return None
    return int((time.time() - _cache_ts) / 60)


def freshness_label() -> str:
    mins = age_minutes()
    if mins is None:
        return "fetching live events…"
    if mins < 1:
        return "live — refreshed just now"
    return f"live — refreshed {mins} min ago"


async def search_live(keywords: str, max_results: int = 15) -> list[dict]:
    """Query getINVOLVED directly (bypasses stale DB)."""
    if not keywords or not keywords.strip():
        if _events and age_minutes() is not None and age_minutes() < 20:
            return _events[:max_results]
        return await asyncio.to_thread(fetch_upcoming_events, max_results)
    return await asyncio.to_thread(search_getinvolved_events, keywords.strip(), max_results)


def events_within_days(days: int = 7) -> list[dict]:
    cutoff = date.today()
    end = cutoff + timedelta(days=days)
    out = []
    for e in _events:
        try:
            d = date.fromisoformat(e.get("date", ""))
        except ValueError:
            continue
        if cutoff <= d <= end:
            out.append(e)
    return out
