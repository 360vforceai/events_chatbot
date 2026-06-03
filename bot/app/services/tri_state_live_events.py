"""Live tri-state concerts, sports, comedy via Ticketmaster Discovery API."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote_plus

import requests

from app.config import settings
from app.services.ticket_service import build_purchase_links

logger = logging.getLogger("discord_bot")

TM_EVENTS_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

# Metro areas reachable from Rutgers
METROS = [
    {"city": "New York", "stateCode": "NY"},
    {"city": "Newark", "stateCode": "NJ"},
    {"city": "New Brunswick", "stateCode": "NJ"},
    {"city": "Philadelphia", "stateCode": "PA"},
    {"city": "Jersey City", "stateCode": "NJ"},
]

CATEGORY_CLASSIFICATIONS = {
    "sports": "Sports",
    "concert": "Music",
    "comedy": "Arts & Theatre",
    "theater": "Arts & Theatre",
    "festival": "Miscellaneous",
    "all": None,
}


def _tm_headers() -> dict:
    return {"Accept": "application/json"}


def _parse_tm_event(item: dict, metro: dict) -> dict | None:
    dates = item.get("dates", {}).get("start", {})
    local_date = dates.get("localDate")
    local_time = dates.get("localTime", "TBD")
    if not local_date:
        return None

    venues = item.get("_embedded", {}).get("venues", [])
    venue = venues[0] if venues else {}
    venue_name = venue.get("name", "TBD")
    city = venue.get("city", {}).get("name") or metro.get("city", "")
    state = venue.get("state", {}).get("stateCode") or metro.get("stateCode", "")

    price_ranges = item.get("priceRanges") or []
    price_tip = ""
    if price_ranges:
        pr = price_ranges[0]
        min_p = pr.get("min")
        max_p = pr.get("max")
        if min_p is not None:
            price_tip = f"From ${min_p:.0f}" + (f"–${max_p:.0f}" if max_p else "")

    tm_url = item.get("url", "")
    title = item.get("name", "Event")
    search_query = f"{title} tickets {city}"

    return {
        "event_id": f"tm-{item.get('id', title)}",
        "title": title,
        "description": (item.get("info") or item.get("pleaseNote") or "")[:300],
        "date": local_date,
        "time": local_time,
        "location": venue_name,
        "campus": f"{city}, {state}",
        "type": "tri_state",
        "category": (item.get("classifications") or [{}])[0].get("segment", {}).get("name", "Event"),
        "club_name": "",
        "free_food": False,
        "rsvp_link": tm_url,
        "price_tip": price_tip,
        "ticket_links": build_purchase_links(search_query),
        "source": "ticketmaster",
    }


def fetch_live_tri_state_events(
    *,
    category: str = "all",
    max_per_metro: int = 8,
) -> list[dict]:
    """Pull real events from Ticketmaster (requires TICKETMASTER_API_KEY)."""
    api_key = (settings.ticketmaster_api_key or "").strip()
    if not api_key:
        return []

    classification = CATEGORY_CLASSIFICATIONS.get(category, category)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    seen: set[str] = set()
    events: list[dict] = []

    for metro in METROS:
        params = {
            "apikey": api_key,
            "city": metro["city"],
            "stateCode": metro["stateCode"],
            "startDateTime": now,
            "sort": "date,asc",
            "size": max_per_metro,
            "countryCode": "US",
        }
        if classification:
            params["classificationName"] = classification

        try:
            resp = requests.get(TM_EVENTS_URL, params=params, headers=_tm_headers(), timeout=12)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("_embedded", {}).get("events", []):
                eid = item.get("id")
                if eid in seen:
                    continue
                parsed = _parse_tm_event(item, metro)
                if not parsed:
                    continue
                seen.add(eid)
                events.append(parsed)
        except Exception as e:
            logger.warning(
                "Ticketmaster fetch failed %s, %s: %s",
                metro["city"],
                metro["stateCode"],
                e,
            )

    events.sort(key=lambda e: (e.get("date", ""), e.get("time", "")))
    return events


def events_within_days(events: list[dict], days: int = 7) -> list[dict]:
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
