import logging
from app.db.client import get_supabase
from app.services.club_search import (
    CLUB_LIST_LIMIT,
    expand_search_terms,
    get_instagram_link,
    rank_clubs,
)
from app.scrapers.getinvolved import search_getinvolved_organizations
from app.services import live_events_cache, data_sync

logger = logging.getLogger("discord_bot")


def _fts_keywords(keywords: str) -> str:
    """PostgreSQL tsquery: OR between words (broader recall than AND)."""
    words = [w.strip() for w in keywords.split() if w.strip()]
    return " | ".join(words) if words else keywords


def _dedupe_clubs(clubs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for club in clubs:
        cid = club.get("club_id") or club.get("name")
        if cid in seen:
            continue
        seen.add(cid)
        out.append(club)
    return out


async def search_clubs(keywords: str, limit: int = CLUB_LIST_LIMIT) -> list:
    terms = expand_search_terms(keywords)
    merged: list[dict] = []

    try:
        # 1. Live getINVOLVED search (best for "computer science", acronyms, etc.)
        for term in terms[:4]:
            merged.extend(search_getinvolved_organizations(term, max_results=limit))
        merged = _dedupe_clubs(merged)

        supabase = get_supabase()

        # 2. Supabase full-text and substring passes
        for term in terms:
            try:
                query = _fts_keywords(term)
                for column in ("name", "description"):
                    results = (
                        supabase.table("clubs")
                        .select("*")
                        .text_search(column, query)
                        .limit(limit)
                        .execute()
                        .data
                    )
                    merged.extend(results or [])
            except Exception:
                pass

        try:
            all_clubs = supabase.table("clubs").select("*").execute().data or []
            for club in all_clubs:
                text = " ".join(
                    [
                        (club.get("name") or "").lower(),
                        (club.get("description") or "").lower(),
                        " ".join(str(c).lower() for c in (club.get("category") or [])),
                        " ".join(str(t).lower() for t in (club.get("tags") or [])),
                    ]
                )
                if any(t in text for t in terms):
                    merged.append(club)
        except Exception:
            pass

        merged = _dedupe_clubs(merged)
        ranked = rank_clubs(merged, terms, limit=limit)
        if ranked:
            return ranked

        if not keywords or not keywords.strip():
            return (supabase.table("clubs").select("*").limit(limit).execute().data) or []

        return (supabase.table("clubs").select("*").limit(limit).execute().data) or []

    except Exception as e:
        logger.error(f"Clubs search error: {e}")
        return []


async def find_club_by_name(name: str) -> dict | None:
    """Resolve a club by exact or close name match (for /instagram, /search)."""
    if not name or not name.strip():
        return None
    needle = name.strip().lower()

    try:
        supabase = get_supabase()
        all_clubs = supabase.table("clubs").select("*").execute().data or []
        for club in all_clubs:
            if (club.get("name") or "").strip().lower() == needle:
                return club

        partial = [
            c
            for c in all_clubs
            if needle in (c.get("name") or "").lower()
            or (c.get("name") or "").lower() in needle
        ]
        if len(partial) == 1:
            return partial[0]
        if partial:
            partial.sort(key=lambda c: abs(len(c.get("name", "")) - len(name)))
            return partial[0]
    except Exception as e:
        logger.error(f"find_club_by_name supabase error: {e}")

    remote = search_getinvolved_organizations(name, max_results=5)
    for club in remote:
        if needle in (club.get("name") or "").lower():
            return club
    return remote[0] if remote else None


def format_clubs_context(results: list) -> str:
    if not results:
        return "No matching clubs in the current search results."
    lines = [
        f"Showing {len(results)} club(s) from search (Rutgers has many more on getINVOLVED):",
    ]
    for club in results:
        links = club.get("links") or {}
        extras = []
        if links.get("getinvolved"):
            extras.append(f"getINVOLVED: {links['getinvolved']}")
        if links.get("instagram"):
            extras.append(f"Instagram: {links['instagram']}")
        if links.get("website"):
            extras.append(f"Website: {links['website']}")
        cats = club.get("category") or []
        cat_str = f" | Categories: {', '.join(str(c) for c in cats[:3])}" if cats else ""
        link_str = f" | {' | '.join(extras)}" if extras else ""
        lines.append(
            f"- {club.get('name')} (Campus: {club.get('campus')}){cat_str}: "
            f"{(club.get('description') or '')[:400]}{link_str}"
        )
    return "\n".join(lines)


def format_instagram_message(club: dict) -> str:
    name = club.get("name", "Unknown club")
    links = club.get("links") or {}
    ig = get_instagram_link(club)
    gi = links.get("getinvolved") or ""
    lines = [f"**{name}**"]
    if ig:
        lines.append(f"Instagram: {ig}")
    else:
        lines.append(
            "No Instagram link on file yet. Check their getINVOLVED page — "
            "run the scraper after they add social links, or look for handles in the description."
        )
    if gi:
        lines.append(f"getINVOLVED: {gi}")
    if links.get("website"):
        lines.append(f"Website: {links['website']}")
    cats = club.get("category") or []
    if cats:
        lines.append(f"Categories: {', '.join(str(c) for c in cats[:4])}")
    return "\n".join(lines)


def _dedupe_events(events: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for e in events:
        key = e.get("event_id") or f"{e.get('title')}|{e.get('date')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


async def search_events(keywords: str, limit: int = 10) -> list:
    """Merge live getINVOLVED results with Supabase for up-to-date answers."""
    merged: list[dict] = []

    try:
        live = await live_events_cache.search_live(keywords, max_results=limit)
        merged.extend(live or [])
    except Exception as e:
        logger.warning("Live events search failed: %s", e)

    try:
        supabase = get_supabase()
        kw = (keywords or "").strip().lower()

        if not kw:
            db_rows = (
                supabase.table("events").select("*").order("date", desc=False).limit(limit).execute().data
            )
        else:
            db_rows = []
            try:
                all_events = supabase.table("events").select("*").order("date", desc=True).execute().data or []
                db_rows = [e for e in all_events if kw in (e.get("club_name") or "").lower()]
            except Exception:
                pass
            if not db_rows:
                try:
                    query = _fts_keywords(keywords)
                    db_rows = (
                        supabase.table("events")
                        .select("*")
                        .text_search("title", query)
                        .limit(limit)
                        .execute()
                        .data
                    )
                except Exception:
                    pass
            if not db_rows:
                db_rows = (
                    supabase.table("events").select("*").order("date", desc=True).limit(limit).execute().data
                )
        merged.extend(db_rows or [])
    except Exception as e:
        logger.error("Supabase events search error: %s", e)

    return _dedupe_events(merged)[:limit]


def format_events_context(results: list) -> str:
    if not results:
        return (
            f"No relevant events found. ({live_events_cache.freshness_label()}, "
            f"database {data_sync.freshness_label()})"
        )
    lines = [f"_Data: {live_events_cache.freshness_label()} · {data_sync.freshness_label()}_"]
    for event in results:
        free_food = " 🍕 Free food!" if event.get("free_food") else ""
        rsvp = f" | RSVP: {event['rsvp_link']}" if event.get("rsvp_link") else ""
        club = f" | Club: {event['club_name']}" if event.get("club_name") else ""
        lines.append(
            f"- {event.get('title')} on {event.get('date')} at {event.get('time')} "
            f"(Location: {event.get('location')}){club}{free_food}{rsvp}"
        )
    return "\n".join(lines)


def format_whats_new(events: list) -> str:
    if not events:
        return (
            "**Nothing on the calendar** for the next 7 days in our live feed.\n"
            f"_{live_events_cache.freshness_label()} · {data_sync.freshness_label()}_\n"
            "Try `/events` with a club name or `/ask` for broader help."
        )
    lines = [
        "**Upcoming this week** (live getINVOLVED)",
        f"_{live_events_cache.freshness_label()} · {data_sync.freshness_label()}_\n",
    ]
    for event in events[:12]:
        free_food = " 🍕" if event.get("free_food") else ""
        rsvp = event.get("rsvp_link", "")
        link = f" · [RSVP]({rsvp})" if rsvp else ""
        lines.append(
            f"• **{event.get('title')}** — {event.get('date')} {event.get('time', '')} "
            f"@ {event.get('location', 'TBD')}{link}{free_food}"
        )
        if event.get("club_name"):
            lines.append(f"  _{event['club_name']}_")
    return "\n".join(lines)
