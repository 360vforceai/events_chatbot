"""In-memory club name cache for Discord autocomplete."""

import time
import logging

logger = logging.getLogger("discord_bot")

_club_cache: list[str] = []
_club_cache_ts: float = 0
_CACHE_TTL = 300  # seconds


def invalidate() -> None:
    global _club_cache_ts
    _club_cache_ts = 0


async def get_club_names() -> list[str]:
    global _club_cache, _club_cache_ts
    if time.time() - _club_cache_ts < _CACHE_TTL and _club_cache:
        return _club_cache
    try:
        from app.db.client import get_supabase
        sb = get_supabase()
        rows = sb.table("clubs").select("name").execute().data
        _club_cache = sorted(r["name"].strip() for r in rows if r.get("name"))
        _club_cache_ts = time.time()
        logger.info("Club autocomplete cache refreshed (%s clubs)", len(_club_cache))
    except Exception as e:
        logger.error("Failed to refresh club cache: %s", e)
    return _club_cache
