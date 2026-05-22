import logging
from app.db.client import get_supabase
from app.config import settings

logger = logging.getLogger("discord_bot")

async def search_clubs(keywords: str) -> list:
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

def format_clubs_context(results: list) -> str:
    if not results:
        return "No relevant clubs found."
    
    context = []
    for club in results:
        context.append(f"- {club.get('name')} (Campus: {club.get('campus')}): {club.get('description')}")
    return "\n".join(context)

async def search_events(keywords: str) -> list:
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

def format_events_context(results: list) -> str:
    if not results:
        return "No relevant events found."
    
    context = []
    for event in results:
        context.append(f"- {event.get('title')} on {event.get('date')} at {event.get('time')} (Location: {event.get('location')})")
    return "\n".join(context)