"""Agent coach — multi-turn narrowing to one event/club/plan recommendation."""

from __future__ import annotations

import asyncio
import logging

from app.services.ai_client import get_coach_agent_response
from app.services.coach_session_service import (
    MAX_TURNS,
    CoachSession,
    end_session,
    mark_resolved,
)
from app.services.events_client import (
    format_clubs_context,
    format_events_context,
    search_clubs,
    search_events,
)
from app.services import live_events_cache
from app.services.ticket_service import format_purchase_links_block

logger = logging.getLogger("discord_bot")

DOMAIN_LABELS = {
    "campus": "Rutgers campus (clubs & events)",
    "tri_state": "Tri-state shows & tickets",
    "date": "Date ideas near Rutgers",
    "general": "Campus life & events",
}


async def _gather_context(session: CoachSession, latest_message: str) -> dict:
    keywords = latest_message or session.goal
    domain = session.domain

    async def campus():
        if domain not in ("campus", "general"):
            return "", ""
        clubs, events = await asyncio.gather(
            search_clubs(keywords, limit=12),
            search_events(keywords, limit=10),
        )
        return format_clubs_context(clubs), format_events_context(events)

    async def tri_state():
        if domain not in ("tri_state", "general"):
            return ""
        events = await live_events_cache.search_tri_state_live(category="all", max_results=8)
        if not events:
            return live_events_cache.tri_state_freshness_label()
        lines = [f"Live tri-state listings ({live_events_cache.tri_state_freshness_label()}):"]
        for e in events[:8]:
            lines.append(
                f"- {e.get('title')} on {e.get('date')} @ {e.get('campus')} "
                f"[tickets]({e.get('rsvp_link')})"
            )
        return "\n".join(lines)

    (clubs_ctx, events_ctx), tri_ctx = await asyncio.gather(campus(), tri_state())
    return {
        "clubs_context": clubs_ctx,
        "events_context": events_ctx,
        "tri_state_context": tri_ctx,
        "freshness": live_events_cache.freshness_label(),
    }


def _format_top_pick(pick: dict) -> str:
    if not pick:
        return ""
    lines = [
        "",
        "━━━━━━━━━━━━━━━━",
        f"## ✅ Your pick: **{pick.get('title', 'Recommendation')}**",
        pick.get("why", ""),
    ]
    when = pick.get("when")
    where = pick.get("where")
    cost = pick.get("cost_tip")
    if when:
        lines.append(f"**When:** {when}")
    if where:
        lines.append(f"**Where:** {where}")
    if cost:
        lines.append(f"**Budget tip:** {cost}")
    direct = pick.get("direct_link")
    if direct:
        label = pick.get("link_label") or "Link"
        lines.append(f"**{label}:** {direct}")
    search_query = pick.get("search_query")
    if search_query:
        lines.append("")
        lines.append(format_purchase_links_block(search_query, heading="Compare tickets & plans"))
    next_steps = pick.get("next_steps") or []
    if next_steps:
        lines.append("\n**Next steps**")
        for step in next_steps[:3]:
            lines.append(f"• {step}")
    lines.append("━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_coach_reply(data: dict, session: CoachSession) -> str:
    parts = [data.get("reply", "").strip()]
    understanding = data.get("understanding")
    if understanding and session.turn_count <= 2:
        parts.append(f"\n_My read so far:_ {understanding}")

    alternatives = data.get("alternatives") or []
    if alternatives and data.get("status") != "resolved":
        parts.append("\n**Also considering**")
        for alt in alternatives[:2]:
            parts.append(f"• **{alt.get('title', 'Option')}** — {alt.get('why', '')}")

    follow_up = data.get("follow_up_prompt")
    if follow_up and data.get("status") != "resolved":
        parts.append(f"\n💬 _{follow_up}_")

    top_pick = data.get("top_pick")
    if top_pick and data.get("status") == "resolved":
        parts.append(_format_top_pick(top_pick))
        parts.append(
            "\n_Session complete — you can keep asking in this thread, "
            "or `/end_session` and `/find` a new goal._"
        )
    elif session.turn_count >= MAX_TURNS - 2:
        parts.append(
            "\n_We're close — share any last preferences and I'll lock in one pick._"
        )

    return "\n\n".join(p for p in parts if p)


async def run_coach_turn(session: CoachSession, user_message: str) -> str:
    if session.status == "ended":
        return "This session ended. Start fresh with `/find <your goal>`."

    if session.turn_count >= MAX_TURNS:
        end_session(session.user_id)
        return (
            "This session hit the turn limit. Use `/end_session` and `/find` "
            "with a refined goal to start again."
        )

    session.add_message("user", user_message)
    context = await _gather_context(session, user_message)

    try:
        data = await get_coach_agent_response(
            goal=session.goal,
            domain=session.domain,
            history=session.history_for_ai()[:-1],
            user_message=user_message,
            context=context,
        )
    except Exception as e:
        logger.error("Coach agent error: %s", e)
        reply = (
            "I hit a snag reaching the AI service. Try again in a moment, "
            "or use `/tickets` / `/events` for direct lookups."
        )
        session.add_message("assistant", reply)
        return reply

    reply = format_coach_reply(data, session)
    session.add_message("assistant", reply)

    if data.get("status") == "resolved":
        mark_resolved(session.user_id)

    return reply


async def start_coach_session(session: CoachSession) -> str:
    opener = (
        f"I want help finding one clear recommendation for this goal: {session.goal}"
    )
    return await run_coach_turn(session, opener)
