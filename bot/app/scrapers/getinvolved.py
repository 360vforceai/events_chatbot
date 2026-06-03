import re
import time
import requests
import uuid
import logging
from datetime import date, datetime, timezone
from app.db.client import get_supabase
from app.services.club_search import extract_social_links

logger = logging.getLogger("discord_bot")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

EVENTS_API = "https://rutgers.campuslabs.com/engage/api/discovery/event/search"
ORGS_API = "https://rutgers.campuslabs.com/engage/api/discovery/search/organizations"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def _event_item_to_dict(item: dict) -> dict | None:
    start_dt = item.get("startsOn")
    if not start_dt:
        return None
    try:
        parsed = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
        date_val = parsed.strftime("%Y-%m-%d")
        time_val = parsed.strftime("%I:%M %p")
    except Exception:
        return None

    benefits = [b.lower() for b in item.get("benefitNames", [])]
    return {
        "event_id": f"gi-{item.get('id', str(uuid.uuid4())[:8])}",
        "title": item.get("name", "No Title"),
        "description": item.get("description", ""),
        "date": date_val,
        "time": time_val,
        "location": item.get("location", "TBD"),
        "campus": "Unknown",
        "type": "club_event",
        "free_food": "free food" in benefits,
        "club_name": item.get("organizationName", ""),
        "rsvp_link": f"https://rutgers.campuslabs.com/engage/event/{item['id']}" if item.get("id") else "",
        "_starts_on": parsed,
    }


def _is_upcoming(event: dict) -> bool:
    starts = event.get("_starts_on")
    if starts:
        now = datetime.now(timezone.utc)
        if starts.tzinfo is None:
            starts = starts.replace(tzinfo=timezone.utc)
        return starts >= now
    try:
        return date.fromisoformat(event.get("date", "")) >= date.today()
    except ValueError:
        return False


def _strip_internal_fields(events: list[dict]) -> list[dict]:
    out = []
    for e in events:
        clean = {k: v for k, v in e.items() if not k.startswith("_")}
        out.append(clean)
    return out


def _fetch_events_from_api(
    *,
    query: str = "",
    order_direction: str = "ascending",
    max_results: int = 100,
    upcoming_only: bool = False,
) -> list[dict]:
    PAGE_SIZE = min(100, max_results)
    events: list[dict] = []
    skip = 0

    try:
        while len(events) < max_results:
            params = {
                "orderByField": "startsOn",
                "orderByDirection": order_direction,
                "status": "Approved",
                "take": PAGE_SIZE,
                "skip": skip,
                "query": query.strip(),
            }
            response = requests.get(EVENTS_API, headers=HEADERS, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            page = data.get("value", [])
            if not page:
                break

            for item in page:
                parsed = _event_item_to_dict(item)
                if not parsed:
                    continue
                if upcoming_only and not _is_upcoming(parsed):
                    continue
                events.append(parsed)
                if len(events) >= max_results:
                    break

            skip += PAGE_SIZE
            total = data.get("@odata.count", 0)
            if skip >= total:
                break

        return _strip_internal_fields(events)
    except Exception as e:
        logger.error("GetInvolved events fetch failed query=%r: %s", query, e)
        return []


def search_getinvolved_events(query: str, max_results: int = 25) -> list[dict]:
    """Live event search from getINVOLVED (real-time)."""
    if not query or not query.strip():
        return fetch_upcoming_events(max_results=max_results)
    return _fetch_events_from_api(
        query=query,
        order_direction="ascending",
        max_results=max_results,
        upcoming_only=True,
    )


def fetch_upcoming_events(max_results: int = 60) -> list[dict]:
    """Upcoming approved events, soonest first."""
    return _fetch_events_from_api(
        query="",
        order_direction="ascending",
        max_results=max_results,
        upcoming_only=True,
    )


def fetch_getinvolved_events() -> list:
    """Full sync: recent + upcoming events for Supabase (descending, last year+)."""
    PAGE_SIZE = 100
    CUTOFF_YEAR = datetime.now().year - 1
    events = []
    skip = 0

    try:
        while True:
            params = {
                "orderByField": "startsOn",
                "orderByDirection": "descending",
                "status": "Approved",
                "take": PAGE_SIZE,
                "skip": skip,
                "query": "",
            }
            response = requests.get(EVENTS_API, headers=HEADERS, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            page = data.get("value", [])
            if not page:
                break

            stop = False
            for item in page:
                parsed = _event_item_to_dict(item)
                if not parsed:
                    continue
                starts = parsed.get("_starts_on")
                if starts and starts.year < CUTOFF_YEAR:
                    stop = True
                    break
                events.append(parsed)

            if stop:
                break

            skip += PAGE_SIZE
            total = data.get("@odata.count", 0)
            if skip >= total:
                break

        return _strip_internal_fields(events)
    except Exception as e:
        logger.error(f"Failed to fetch GetInvolved events: {e}")
        return []


def save_events_to_supabase(events: list):
    if not events:
        return
    try:
        supabase = get_supabase()
        for event in events:
            supabase.table("events").upsert(event).execute()
        logger.info(f"Saved {len(events)} events from GetInvolved to Supabase.")
    except Exception as e:
        logger.error(f"Failed to save GetInvolved events: {e}")


# ---------------------------------------------------------------------------
# Clubs / Organizations
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _org_item_to_club(item: dict) -> dict:
    raw_desc = item.get("Summary") or item.get("Description") or ""
    social = extract_social_links(raw_desc)
    website_key = item.get("WebsiteKey", item["Id"])
    links = {
        "getinvolved": f"https://rutgers.campuslabs.com/engage/organization/{website_key}",
        **social,
    }
    return {
        "club_id": f"gi-org-{item['Id']}",
        "name": item.get("Name", "Unknown Club"),
        "description": _strip_html(raw_desc),
        "category": item.get("CategoryNames", []),
        "campus": "Rutgers",
        "meeting_time": None,
        "links": links,
        "tags": item.get("CategoryNames", []),
    }


def search_getinvolved_organizations(query: str, max_results: int = 25) -> list[dict]:
    """Live search against getINVOLVED (better recall than local FTS alone)."""
    if not query or not query.strip():
        return []
    PAGE_SIZE = 25
    clubs: list[dict] = []
    skip = 0
    try:
        while len(clubs) < max_results:
            response = requests.get(
                ORGS_API,
                headers=HEADERS,
                params={"take": PAGE_SIZE, "query": query.strip(), "skip": skip},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            page = data.get("value", [])
            if not page:
                break
            for item in page:
                if item.get("Status") != "Active":
                    continue
                clubs.append(_org_item_to_club(item))
                if len(clubs) >= max_results:
                    break
            skip += PAGE_SIZE
            total = data.get("@odata.count", 0)
            if skip >= total:
                break
        return clubs
    except Exception as e:
        logger.error(f"GetInvolved org search failed query={query!r}: {e}")
        return []


def fetch_getinvolved_clubs() -> list:
    """Fetches all organizations from the getINVOLVED search API (paginated, max 25/page)."""
    PAGE_SIZE = 25
    clubs = []
    skip = 0

    try:
        while True:
            response = requests.get(
                ORGS_API,
                headers=HEADERS,
                params={"take": PAGE_SIZE, "query": "", "skip": skip},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            page = data.get("value", [])
            if not page:
                break

            for item in page:
                if item.get("Status") != "Active":
                    continue
                clubs.append(_org_item_to_club(item))

            skip += PAGE_SIZE
            total = data.get("@odata.count", 0)
            if skip >= total:
                break

        return clubs
    except Exception as e:
        logger.error(f"Failed to fetch GetInvolved clubs: {e}")
        return []


def save_clubs_to_supabase(clubs: list):
    if not clubs:
        return
    try:
        supabase = get_supabase()
        for club in clubs:
            supabase.table("clubs").upsert(club).execute()
        logger.info(f"Saved {len(clubs)} clubs from GetInvolved to Supabase.")
    except Exception as e:
        logger.error(f"Failed to save GetInvolved clubs: {e}")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def run():
    """Scrape and save both events and clubs."""
    events = fetch_getinvolved_events()
    save_events_to_supabase(events)

    clubs = fetch_getinvolved_clubs()
    save_clubs_to_supabase(clubs)

    return {"events": len(events), "clubs": len(clubs)}


if __name__ == "__main__":
    print(run())
