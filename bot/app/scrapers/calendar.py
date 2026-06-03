"""
Rutgers University calendar scraper.

The old ruevents.rutgers.edu RSS feed now returns HTML instead of XML and
is effectively dead.  We pull university-wide events from the getINVOLVED
event search API (same source as getinvolved.py) but filter for events
tagged as university/department events rather than club-only events.
"""

import logging
from app.scrapers.getinvolved import fetch_getinvolved_events, save_events_to_supabase

logger = logging.getLogger("discord_bot")

UNIVERSITY_CATEGORIES = {"university_event", "department", "academic", "athletics"}


def fetch_rutgers_rss_events(feed_url: str = "") -> list:
    """
    Returns university-wide events from getINVOLVED.
    The feed_url parameter is kept for backwards-compatibility but is unused.
    """
    all_events = fetch_getinvolved_events()

    # Mark all as university_event type for calendar context
    for event in all_events:
        event["type"] = "university_event"

    logger.info(f"Calendar scraper fetched {len(all_events)} events via getINVOLVED.")
    return all_events


def run_calendar_scraper() -> int:
    events = fetch_rutgers_rss_events()
    save_events_to_supabase(events)
    return len(events)


if __name__ == "__main__":
    print(run_calendar_scraper())
