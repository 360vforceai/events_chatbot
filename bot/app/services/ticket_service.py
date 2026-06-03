"""Tri-state (NY / NJ / PA) event discovery and ticket purchase link helpers."""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from app.services.ai_client import get_tri_state_ask_response, get_tri_state_recommendations

logger = logging.getLogger("discord_bot")

TRI_STATE_NOTE = (
    "Coverage: NYC, North/Central NJ (New Brunswick, Newark, Jersey City), "
    "and greater Philadelphia — easy from Rutgers."
)

# Discord slash command choices
EVENT_CATEGORIES = {
    "sports": "Sports (Rutgers, NFL, NBA, NHL, MLS, college)",
    "concert": "Concerts & live music",
    "comedy": "Comedy & stand-up",
    "theater": "Theater & Broadway",
    "festival": "Festivals & outdoor events",
    "all": "All event types",
}

DEFAULT_SEARCH_BY_CATEGORY = {
    "sports": "Rutgers Scarlet Knights tickets New Jersey",
    "concert": "concerts New York Newark cheap tickets",
    "comedy": "comedy shows New York Newark student",
    "theater": "Broadway discount tickets NYC",
    "festival": "music festivals tri-state area",
    "all": "events New York New Jersey Philadelphia tickets",
}


def _encode(q: str) -> str:
    return quote_plus(q.strip())


def build_purchase_links(search_query: str) -> list[dict[str, str]]:
    """Resale / primary marketplaces where students can compare and buy tickets."""
    q = _encode(search_query)
    return [
        {
            "label": "SeatGeek",
            "url": f"https://seatgeek.com/search?search={q}",
            "note": "Deal scores & mobile tickets",
        },
        {
            "label": "Gametime",
            "url": f"https://gametime.co/search?q={q}",
            "note": "Often below face value, last-minute",
        },
        {
            "label": "StubHub",
            "url": f"https://www.stubhub.com/search/?q={q}",
            "note": "Large resale inventory",
        },
        {
            "label": "Vivid Seats",
            "url": f"https://www.vividseats.com/search?searchTerm={q}",
            "note": "Frequent promos",
        },
        {
            "label": "Ticketmaster",
            "url": f"https://www.ticketmaster.com/search?q={q}",
            "note": "Official primary tickets",
        },
        {
            "label": "TodayTix",
            "url": f"https://www.todaytix.com/nyc/shows?q={q}",
            "note": "NYC theater & comedy discounts",
        },
    ]


def _format_link_line(vendor: dict[str, str]) -> str:
    return f"• [{vendor['label']}]({vendor['url']}) — _{vendor['note']}_"


def format_purchase_links_block(search_query: str, heading: str = "Buy tickets") -> str:
    lines = [f"**{heading}** _(search: {search_query})_"]
    for vendor in build_purchase_links(search_query):
        lines.append(_format_link_line(vendor))
    return "\n".join(lines)


def _resolve_search_query(category: str, search: str | None) -> str:
    cat = (category or "all").lower()
    custom = (search or "").strip()
    if custom:
        base = DEFAULT_SEARCH_BY_CATEGORY.get(cat, DEFAULT_SEARCH_BY_CATEGORY["all"])
        # Keep user query primary; add tri-state hint if missing geo words
        geo_hints = ("new york", "nyc", "nj", "new jersey", "philadelphia", "philly", "newark")
        if not any(g in custom.lower() for g in geo_hints):
            return f"{custom} tickets tri-state"
        return f"{custom} tickets"
    return DEFAULT_SEARCH_BY_CATEGORY.get(cat, DEFAULT_SEARCH_BY_CATEGORY["all"])


def format_pick(pick: dict, index: int) -> str:
    title = pick.get("title", "Event")
    venue = pick.get("venue", "")
    area = pick.get("area", "")
    timing = pick.get("timing", "")
    price_tip = pick.get("price_tip", "")
    query = pick.get("search_query") or title

    header = f"**{index}. {title}**"
    meta_parts = [p for p in [venue, area, timing] if p]
    meta = " · ".join(meta_parts)
    lines = [header]
    if meta:
        lines.append(meta)
    if price_tip:
        lines.append(f"💰 {price_tip}")
    lines.append(format_purchase_links_block(query, heading="Get tickets"))
    return "\n\n".join(lines)


def format_tri_state_response(data: dict, *, category: str, search_query: str) -> str:
    parts = [f"**Tri-state events & tickets** — _{EVENT_CATEGORIES.get(category, category)}_"]
    parts.append(f"_{TRI_STATE_NOTE}_")

    intro = data.get("intro")
    if intro:
        parts.append(intro)

    picks = data.get("picks") or []
    if picks:
        parts.append("\n**Suggested picks**")
        for i, pick in enumerate(picks[:6], start=1):
            parts.append(format_pick(pick, i))
    else:
        parts.append("\n**Search all marketplaces**")
        parts.append(format_purchase_links_block(search_query, heading="Compare prices & buy"))

    tips = data.get("money_saving_tips") or []
    if tips:
        parts.append("\n**Student budget tips**")
        for tip in tips[:5]:
            parts.append(f"• {tip}")

    parts.append(
        "\n_Prices change quickly — compare sites above before buying. "
        "Verify date/venue on the ticket page at checkout._"
    )
    return "\n\n".join(parts)


async def find_cheap_tickets(
    category: str,
    search: str | None = None,
    budget: str | None = None,
) -> str:
    """Cheap-ticket search for a category (sports, concert, comedy, etc.)."""
    import asyncio

    from app.services.ticket_price_compare import format_cheapest_tri_state_report

    search_query = _resolve_search_query(category, search)
    price_block = await asyncio.to_thread(
        format_cheapest_tri_state_report,
        keyword=search or "",
        category=category,
        budget=budget,
        limit=6,
    )
    live_block = await _format_live_tri_state_block(category)
    try:
        data = await get_tri_state_recommendations(
            mode="tickets",
            category=category,
            interests="",
            search=search or "",
            budget=budget or "",
            rutgers_events_context="",
            search_query=search_query,
        )
        body = format_tri_state_response(data, category=category, search_query=search_query)
        parts = [p for p in [price_block, live_block, body] if p]
        return "\n\n".join(parts)
    except Exception as e:
        logger.error(f"find_cheap_tickets AI fallback: {e}")
        budget_line = f"\nBudget: {budget}" if budget else ""
        base = (
            f"**Tri-state cheap tickets** — _{EVENT_CATEGORIES.get(category, category)}_{budget_line}\n"
            f"_{TRI_STATE_NOTE}_\n\n"
            f"{format_purchase_links_block(search_query, heading='Compare & buy tickets')}\n\n"
            "_AI suggestions are temporarily unavailable — use the links above to shop._"
        )
        parts = [p for p in [price_block, live_block, base] if p]
        return "\n\n".join(parts)


async def compare_ticket_prices(
    search: str,
    category: str = "all",
    budget: str | None = None,
) -> str:
    """Cheapest-first tri-state listings with links to every major ticket site."""
    import asyncio

    from app.services.ticket_price_compare import format_cheapest_tri_state_report

    return await asyncio.to_thread(
        format_cheapest_tri_state_report,
        keyword=search,
        category=category,
        budget=budget,
        limit=10,
    )


async def _format_live_tri_state_block(category: str) -> str:
    from app.services.live_events_cache import search_tri_state_live, tri_state_freshness_label

    events = await search_tri_state_live(category=category, max_results=6)
    if not events:
        hint = tri_state_freshness_label()
        if "TICKETMASTER" in hint:
            return f"_{hint}_"
        return ""
    lines = [f"**Live listings** _({tri_state_freshness_label()})_", ""]
    for e in events[:6]:
        url = e.get("rsvp_link", "")
        link = f" [Tickets]({url})" if url else ""
        lines.append(
            f"• **{e.get('title')}** — {e.get('date')} @ {e.get('campus', '')}{link}"
        )
    return "\n".join(lines)


def format_ask_tri_state_response(data: dict) -> str:
    """Format conversational /ask_tickets reply with optional ticket picks."""
    parts = ["**Tri-state Q&A**", f"_{TRI_STATE_NOTE}_"]

    answer = data.get("answer")
    if answer:
        parts.append(answer)

    picks = data.get("picks") or []
    if picks:
        parts.append("\n**Events & tickets to explore**")
        for i, pick in enumerate(picks[:4], start=1):
            parts.append(format_pick(pick, i))

    tips = data.get("money_saving_tips") or []
    if tips:
        parts.append("\n**Save money**")
        for tip in tips[:4]:
            parts.append(f"• {tip}")

    follow = data.get("follow_up_ideas") or []
    if follow:
        parts.append("\n**Keep exploring**")
        for idea in follow[:4]:
            parts.append(f"• {idea}")

    return "\n\n".join(parts)


async def ask_tri_state_question(question: str, history: list) -> str:
    """Open-ended tri-state ask — develops student interests with optional buy links."""
    try:
        data = await get_tri_state_ask_response(history, question)
        return format_ask_tri_state_response(data)
    except Exception as e:
        logger.error(f"ask_tri_state_question error: {e}")
        fallback_q = _resolve_search_query("all", question)
        return (
            f"**Tri-state Q&A**\n_{TRI_STATE_NOTE}_\n\n"
            "I couldn't reach the AI service right now. Browse tickets here:\n\n"
            f"{format_purchase_links_block(fallback_q, heading='Search tickets')}\n\n"
            "_Try your question again in a moment._"
        )


async def explore_events_by_interests(
    interests: str,
    category: str | None = None,
    budget: str | None = None,
    rutgers_events_context: str = "",
) -> str:
    """Personalized tri-state event discovery from student interests."""
    cat = (category or "all").lower()
    search_query = _resolve_search_query(cat, interests)
    try:
        data = await get_tri_state_recommendations(
            mode="explore",
            category=cat,
            interests=interests,
            search="",
            budget=budget or "",
            rutgers_events_context=rutgers_events_context,
            search_query=search_query,
        )
        body = format_tri_state_response(data, category=cat, search_query=search_query)
        live_block = await _format_live_tri_state_block(cat)
        return f"{live_block}\n\n{body}" if live_block else body
    except Exception as e:
        logger.error(f"explore_events AI fallback: {e}")
        live_block = await _format_live_tri_state_block(cat)
        base = (
            f"**Events for you** — interests: _{interests}_\n"
            f"_{TRI_STATE_NOTE}_\n\n"
            f"{format_purchase_links_block(search_query, heading='Browse tickets')}\n\n"
            "_AI picks are temporarily unavailable — try the links above._"
        )
        return f"{live_block}\n\n{base}" if live_block else base
