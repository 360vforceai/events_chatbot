import logging
from app.db.client import get_supabase
from app.config import settings

logger = logging.getLogger("discord_bot")

async def search_clubs(keywords: str) -> list:
    """
    SUPABASE IMPLEMENTATION NOTE:
    Ensure you have a 'clubs' table in Supabase with at least these columns:
    - club_id (text, primary key)
    - name (text)
    - description (text)
    - campus (text)
    """
    try:
        supabase = get_supabase()
        
        if not keywords:
            response = supabase.table("clubs").select("*").limit(5).execute()
            return response.data
            
        response = (
            supabase.table("clubs")
            .select("*")
            .or_(f"name.ilike.%{keywords}%,description.ilike.%{keywords}%")
            .limit(5)
            .execute()
        )
        return response.data
    except Exception as e:
        logger.error(f"Supabase clubs search error: {e}")
        # Return fallback dummy data if Supabase isn't set up yet
        return [
            {
                "club_id": "dummy-1",
                "name": "Dummy AI Club",
                "description": "We build cool AI bots.",
                "campus": "Busch"
            }
        ]

def format_clubs_context(results: list) -> str:
    if not results:
        return "No relevant clubs found."
    
    context = []
    for club in results:
        context.append(f"- {club.get('name')} (Campus: {club.get('campus')}): {club.get('description')}")
    return "\n".join(context)

async def search_events(keywords: str) -> list:
    """
    SUPABASE IMPLEMENTATION NOTE:
    Ensure you have an 'events' table in Supabase with at least these columns:
    - event_id (text, primary key)
    - title (text)
    - description (text)
    - date (date)
    - time (text)
    - location (text)
    """
    try:
        supabase = get_supabase()
        
        if not keywords:
            response = supabase.table("events").select("*").limit(5).execute()
            return response.data
            
        response = (
            supabase.table("events")
            .select("*")
            .or_(f"title.ilike.%{keywords}%,description.ilike.%{keywords}%")
            .limit(5)
            .execute()
        )
        return response.data
    except Exception as e:
        logger.error(f"Supabase events search error: {e}")
        # Return fallback dummy data if Supabase isn't set up yet
        return [
            {
                "event_id": "evt-dummy-1",
                "title": "Dummy Hackathon",
                "description": "A 24-hour coding event.",
                "date": "2026-10-10",
                "time": "10:00 AM",
                "location": "College Ave Gym"
            }
        ]

def format_events_context(results: list) -> str:
    if not results:
        return "No relevant events found."
    
    context = []
    for event in results:
        context.append(f"- {event.get('title')} on {event.get('date')} at {event.get('time')} (Location: {event.get('location')})")
    return "\n".join(context)