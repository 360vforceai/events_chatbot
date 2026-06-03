"""Background sync state and full getINVOLVED → Supabase refresh."""

from __future__ import annotations

import logging
import time

from app.scrapers import getinvolved

logger = logging.getLogger("discord_bot")

_last_sync_at: float | None = None
_last_sync_stats: dict = {}
_last_sync_error: str | None = None


def run_full_sync() -> dict:
    """Pull latest clubs and events into Supabase."""
    global _last_sync_at, _last_sync_stats, _last_sync_error
    try:
        result = getinvolved.run()
        _last_sync_at = time.time()
        _last_sync_stats = result
        _last_sync_error = None
        logger.info("Data sync complete: %s", result)
        return result
    except Exception as e:
        _last_sync_error = str(e)
        logger.error("Data sync failed: %s", e)
        raise


def freshness_label() -> str:
    if _last_sync_error and not _last_sync_at:
        return "live getINVOLVED API (database sync pending)"
    if _last_sync_at is None:
        return "live getINVOLVED API"
    mins = int((time.time() - _last_sync_at) / 60)
    if mins < 1:
        return "synced just now"
    if mins == 1:
        return "synced 1 min ago"
    return f"synced {mins} min ago"


def last_sync_stats() -> dict:
    return dict(_last_sync_stats)
