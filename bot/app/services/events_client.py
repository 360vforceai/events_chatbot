import logging
from app.db.client import get_supabase

logger = logging.getLogger("discord_bot")


def _fts_keywords(keywords: str) -> str:
    """Convert a keyword string to a PostgreSQL tsquery-compatible format."""
    words = [w.strip() for w in keywords.split() if w.strip()]
    return " & ".join(words) if words else keywords


async def search_clubs(keywords: str) -> list:
    try:
        supabase = get_supabase()

        if not keywords or not keywords.strip():
            return supabase.table("clubs").select("*").limit(5).execute().data

        # 1. Try full-text search on name (works well for multi-word terms)
        try:
            query = _fts_keywords(keywords)
            results = supabase.table("clubs").select("*").text_search("name", query).limit(5).execute().data
            if results:
                return results
        except Exception:
            pass

        # 2. Try full-text search on description
        try:
            query = _fts_keywords(keywords)
            results = supabase.table("clubs").select("*").text_search("description", query).limit(5).execute().data
            if results:
                return results
        except Exception:
            pass

        # 3. Fetch all clubs and filter in Python (handles acronyms like RUMAD, USACS)
        try:
            kw = keywords.strip().lower()
            all_clubs = supabase.table("clubs").select("*").execute().data
            matches = [
                c for c in all_clubs
                if kw in (c.get("name") or "").lower()
                or kw in (c.get("description") or "").lower()
            ]
            if matches:
                return matches[:5]
        except Exception:
            pass

        # 4. Final fallback: general sample
        return supabase.table("clubs").select("*").limit(5).execute().data

    except Exception as e:
        logger.error(f"Supabase clubs search error: {e}")
        return []


def format_clubs_context(results: list) -> str:
    if not results:
        return "No relevant clubs found."
    lines = []
    for club in results:
        links = club.get("links") or {}
        url = links.get("getinvolved") or links.get("website") or ""
        link_str = f" | Page: {url}" if url else ""
        lines.append(
            f"- {club.get('name')} (Campus: {club.get('campus')}): "
            f"{club.get('description')}{link_str}"
        )
    return "\n".join(lines)


async def search_events(keywords: str) -> list:
    try:
        supabase = get_supabase()

        if not keywords or not keywords.strip():
            return supabase.table("events").select("*").order("date", desc=True).limit(5).execute().data

        kw = keywords.strip().lower()

        # 1. Search by club_name in Python (exact substring — handles full club names from autocomplete)
        try:
            all_events = supabase.table("events").select("*").order("date", desc=True).execute().data
            club_matches = [e for e in all_events if kw in (e.get("club_name") or "").lower()]
            if club_matches:
                return club_matches[:5]
        except Exception:
            pass

        # 2. FTS on event title
        try:
            query = _fts_keywords(keywords)
            results = supabase.table("events").select("*").text_search("title", query).limit(5).execute().data
            if results:
                return results
        except Exception:
            pass

        # 3. Fallback: upcoming events
        return supabase.table("events").select("*").order("date", desc=True).limit(5).execute().data

    except Exception as e:
        logger.error(f"Supabase events search error: {e}")
        return []


def format_events_context(results: list) -> str:
    if not results:
        return "No relevant events found."
    lines = []
    for event in results:
        free_food = " 🍕 Free food!" if event.get("free_food") else ""
        rsvp = f" | RSVP: {event['rsvp_link']}" if event.get("rsvp_link") else ""
        club = f" | Club: {event['club_name']}" if event.get("club_name") else ""
        lines.append(
            f"- {event.get('title')} on {event.get('date')} at {event.get('time')} "
            f"(Location: {event.get('location')}){club}{free_food}{rsvp}"
        )
    return "\n".join(lines)
