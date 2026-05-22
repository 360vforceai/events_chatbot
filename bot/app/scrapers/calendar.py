import requests
import xml.etree.ElementTree as ET
import uuid
import logging
from datetime import datetime
from app.db.client import get_supabase

logger = logging.getLogger("discord_bot")

def fetch_rutgers_rss_events(feed_url: str) -> list:
    """Fetches and parses a Rutgers XML RSS event feed."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(feed_url, headers=headers)
    
    if response.status_code != 200:
        logger.error(f"Failed to fetch feed: {response.status_code}")
        return []

    root = ET.fromstring(response.content)
    events = []

    for item in root.findall('./channel/item'):
        pub_date_str = item.find('pubDate').text if item.find('pubDate') is not None else ''
        
        # Try to parse pubDate to extract date and time
        # Example format: Wed, 20 May 2026 14:00:00 EST
        date_val = None
        time_val = 'TBD'
        if pub_date_str:
            try:
                # Basic parsing attempt, fallback to string if complex
                parsed_date = datetime.strptime(pub_date_str[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                date_val = parsed_date.strftime("%Y-%m-%d")
                time_val = parsed_date.strftime("%I:%M %p")
            except Exception:
                pass
                
        event = {
            'event_id': f"ru-cal-{str(uuid.uuid4())[:8]}", 
            'title': item.find('title').text if item.find('title') is not None else 'No Title',
            'description': item.find('description').text if item.find('description') is not None else '',
            'date': date_val,
            'time': time_val,
            'location': 'Rutgers University',
            'campus': 'Unknown',
            'type': 'university_event',
            'free_food': False,
            'rsvp_link': item.find('link').text if item.find('link') is not None else ''
        }
        events.append(event)
        
    return events

def save_events_to_supabase(events: list[dict]):
    """Saves the parsed events to the Supabase events table."""
    if not events:
        return
        
    try:
        supabase = get_supabase()
        for event in events:
            supabase.table("events").upsert(event).execute()
        logger.info(f"Saved {len(events)} events from RSS to Supabase.")
    except Exception as e:
        logger.error(f"Failed to save RSS events to Supabase: {e}")

def run_calendar_scraper():
    """Main entry point to run the calendar scraper."""
    feed_url = "https://ruevents.rutgers.edu/events/getEventsRss.xml"
    events = fetch_rutgers_rss_events(feed_url)
    save_events_to_supabase(events)
    return len(events)

if __name__ == "__main__":
    run_calendar_scraper()
