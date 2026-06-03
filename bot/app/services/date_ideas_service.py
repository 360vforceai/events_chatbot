"""Date Ideas — discovery and Q&A for Rutgers / tri-state area."""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from app.services.ai_client import get_date_planning_response

logger = logging.getLogger("discord_bot")

DATE_AREA_NOTE = (
    "Ideas near Rutgers (New Brunswick), with easy trips to NYC, Jersey City, Newark, or Princeton."
)

DATE_VIBES = {
    "casual": "Casual & low-key",
    "active": "Active / walkable",
    "foodie": "Food & coffee",
    "creative": "Arts, games, or creative",
    "outdoors": "Outdoors & nature",
    "nyc_trip": "NYC day or evening trip",
    "any": "Surprise me — any vibe",
}


def _encode(q: str) -> str:
    return quote_plus(q.strip())


def build_date_resource_links(search_query: str, area: str = "New Brunswick NJ") -> list[dict[str, str]]:
    q = _encode(search_query)
    loc = _encode(area)
    return [
        {
            "label": "Google Maps",
            "url": f"https://www.google.com/maps/search/{q}+near+{loc}",
            "note": "Directions & nearby spots",
        },
        {
            "label": "Yelp",
            "url": f"https://www.yelp.com/search?find_desc={q}&find_loc={loc}",
            "note": "Reviews & reservations",
        },
        {
            "label": "OpenTable",
            "url": f"https://www.opentable.com/s?term={q}&covers=2",
            "note": "Restaurant bookings",
        },
        {
            "label": "Eventbrite",
            "url": f"https://www.eventbrite.com/d/nj--new-brunswick/{q}/",
            "note": "Local events & experiences",
        },
    ]


def _format_resource_line(vendor: dict[str, str]) -> str:
    return f"• [{vendor['label']}]({vendor['url']}) — _{vendor['note']}_"


def format_date_links_block(search_query: str, area: str = "New Brunswick NJ") -> str:
    lines = [f"**Plan it** _(search: {search_query})_"]
    for vendor in build_date_resource_links(search_query, area):
        lines.append(_format_resource_line(vendor))
    return "\n".join(lines)


def format_date_idea(idea: dict, index: int) -> str:
    title = idea.get("title", "Date idea")
    desc = idea.get("description", "")
    area = idea.get("area", "")
    timing = idea.get("timing", "")
    cost = idea.get("estimated_cost", "")
    query = idea.get("search_query") or title

    lines = [f"**{index}. {title}**"]
    if desc:
        lines.append(desc)
    meta = " · ".join(p for p in [area, timing, cost] if p)
    if meta:
        lines.append(f"_{meta}_")
    lines.append(format_date_links_block(query, area=area or "New Brunswick NJ"))
    return "\n\n".join(lines)


def format_date_response(data: dict, *, heading: str) -> str:
    parts = [heading, f"_{DATE_AREA_NOTE}_"]

    answer = data.get("answer")
    if answer:
        parts.append(answer)

    ideas = data.get("ideas") or []
    if ideas:
        parts.append("\n**Ideas**")
        for i, idea in enumerate(ideas[:7], start=1):
            parts.append(format_date_idea(idea, i))

    etiquette = data.get("etiquette_tips") or []
    if etiquette:
        parts.append("\n**Tips**")
        for tip in etiquette[:5]:
            parts.append(f"• {tip}")

    follow = data.get("follow_up_ideas") or []
    if follow:
        parts.append("\n**You could also ask**")
        for item in follow[:4]:
            parts.append(f"• {item}")

    parts.append(
        "\n_Pick public places, tell a friend your plans, and leave if you feel uncomfortable._"
    )
    return "\n\n".join(parts)


async def ask_about_first_dates(question: str, history: list) -> str:
    try:
        data = await get_date_planning_response(
            mode="ask",
            question=question,
            history=history,
            vibe="",
            budget="",
            interests="",
        )
        return format_date_response(data, heading="**Date Ideas**")
    except Exception as e:
        logger.error(f"ask_about_first_dates error: {e}")
        return (
            "**Date Ideas**\n"
            f"_{DATE_AREA_NOTE}_\n\n"
            "AI is temporarily unavailable. Try `/date_ideas` with a vibe like `casual` or `foodie`, "
            "or ask again in a moment.\n\n"
            f"{format_date_links_block('coffee shops', area='New Brunswick NJ')}"
        )


async def discover_first_date_ideas(
    vibe: str,
    interests: str | None = None,
    budget: str | None = None,
) -> str:
    try:
        data = await get_date_planning_response(
            mode="discover",
            question="",
            history=[],
            vibe=vibe,
            budget=budget or "",
            interests=interests or "",
        )
        label = DATE_VIBES.get(vibe, vibe)
        return format_date_response(
            data,
            heading=f"**Date Ideas** — _{label}_",
        )
    except Exception as e:
        logger.error(f"discover_first_date_ideas error: {e}")
        return (
            f"**Date Ideas** — _{DATE_VIBES.get(vibe, vibe)}_\n"
            f"_{DATE_AREA_NOTE}_\n\n"
            f"{format_date_links_block(interests or 'date ideas', area='New Brunswick NJ')}\n\n"
            "_AI suggestions unavailable — use links above to browse._"
        )
