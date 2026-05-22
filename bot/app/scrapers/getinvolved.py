import time
import requests
import uuid
import logging
from datetime import datetime
from app.db.client import get_supabase

logger = logging.getLogger("discord_bot")

GETINVOLVED_API_BASE = "https://rutgers.campuslabs.com/engage/api/discovery/event/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

def fetch_getinvolved_events() -> list:
    """Fetches events from the getINVOLVED JSON API."""
    params = {
        "orderByField": "startsOn",
        "orderByDirection": "ascending",
        "status": "Approved",
        "take": 100,
        "query": ""
    }
    
    try:
        response = requests.get(GETINVOLVED_API_BASE, headers=HEADERS, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        raw_events = data.get("value", [])
        events = []
        
        for item in raw_events:
            start_dt = item.get("startsOn")
            date_val = None
            time_val = 'TBD'
            
            if start_dt:
                try:
                    # e.g., "2026-05-20T18:00:00-04:00"
                    parsed_date = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
                    date_val = parsed_date.strftime("%Y-%m-%d")
                    time_val = parsed_date.strftime("%I:%M %p")
                except Exception:
                    pass
            
            event = {
                'event_id': f"gi-{item.get('id', str(uuid.uuid4())[:8])}",
                'title': item.get('name', 'No Title'),
                'description': item.get('description', ''),
                'date': date_val,
                'time': time_val,
                'location': item.get('location', 'TBD'),
                'campus': 'Unknown',
                'type': 'club_event',
                'free_food': False, # Could potentially parse from themes/perks if provided
                'rsvp_link': f"https://rutgers.campuslabs.com/engage/event/{item.get('id')}" if item.get('id') else ''
            }
            events.append(event)
            
        return events
    except Exception as e:
        logger.error(f"Failed to fetch GetInvolved events: {e}")
        return []

def save_events_to_supabase(events: list[dict]):
    if not events:
        return
    try:
        supabase = get_supabase()
        for event in events:
            supabase.table("events").upsert(event).execute()
        logger.info(f"Saved {len(events)} events from GetInvolved to Supabase.")
    except Exception as e:
        logger.error(f"Failed to save GetInvolved events: {e}")

def run():
    events = fetch_getinvolved_events()
    save_events_to_supabase(events)
    return len(events)

if __name__ == "__main__":
    run()
