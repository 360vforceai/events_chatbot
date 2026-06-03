import re
import time
import requests
import uuid
import logging
from datetime import datetime
from app.db.client import get_supabase

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

def fetch_getinvolved_events() -> list:
    """Fetches upcoming/recent events from the getINVOLVED JSON API (paginated)."""
    PAGE_SIZE = 100
    CUTOFF_YEAR = datetime.now().year - 1  # keep events from last year onwards
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
                start_dt = item.get("startsOn")
                date_val = None
                time_val = "TBD"

                if start_dt:
                    try:
                        parsed = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
                        if parsed.year < CUTOFF_YEAR:
                            stop = True
                            break
                        date_val = parsed.strftime("%Y-%m-%d")
                        time_val = parsed.strftime("%I:%M %p")
                    except Exception:
                        continue

                if not date_val:
                    continue

                benefits = [b.lower() for b in item.get("benefitNames", [])]
                events.append({
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
                })

            if stop:
                break

            skip += PAGE_SIZE
            total = data.get("@odata.count", 0)
            if skip >= total:
                break

        return events
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
                clubs.append({
                    "club_id": f"gi-org-{item['Id']}",
                    "name": item.get("Name", "Unknown Club"),
                    "description": _strip_html(item.get("Summary") or item.get("Description", "")),
                    "category": item.get("CategoryNames", []),
                    "campus": "Rutgers",
                    "meeting_time": None,
                    "links": {
                        "getinvolved": f"https://rutgers.campuslabs.com/engage/organization/{item.get('WebsiteKey', item['Id'])}"
                    },
                    "tags": item.get("CategoryNames", []),
                })

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
