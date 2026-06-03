"""Route students to the right slash commands — and into coach sessions when needed."""

from __future__ import annotations

from app.services.coach_session_service import detect_domain, get_session

TOPIC_LABELS = {
    "coach": "Pick one thing with a personal coach",
    "campus_clubs": "Rutgers clubs & organizations",
    "campus_events": "Rutgers campus events",
    "tri_state": "Tri-state tickets & shows (NY / NJ / PA)",
    "date_ideas": "Date ideas near Rutgers",
    "browse": "Browse what's happening",
}


def build_find_goal(topic: str, details: str = "") -> str:
    d = (details or "").strip()
    defaults = {
        "coach": d or "help me pick one clear recommendation for what to do",
        "campus_clubs": d or "find the best Rutgers club for me to join",
        "campus_events": d or "find one Rutgers campus event I should go to",
        "tri_state": d or "find one cheap tri-state show or game I should attend",
        "date_ideas": d or "find one date idea that fits my vibe and budget",
        "browse": d or "help me pick one thing from what's new on campus and tri-state",
    }
    goal = defaults.get(topic, defaults["coach"])
    if d and topic != "coach":
        return f"{goal} — details: {d}"
    return goal


def format_topic_guide(topic: str, details: str = "") -> str:
    d = (details or "").strip()
    lines = [f"**Where to go next** — _{TOPIC_LABELS.get(topic, topic)}_"]

    if topic == "campus_clubs":
        lines += [
            "• `/discover <major> <interests> <goals>` — personalized club list",
            "• `/search <club name>` — look up one organization",
            "• `/instagram <club>` — social + getINVOLVED links",
        ]
        if d:
            lines.append(f"• `/search {d}` — try this now")
        lines.append("• `/ask <question>` — free-form club questions")

    elif topic == "campus_events":
        lines += [
            "• `/whats_new` — next 7 days (campus + tri-state)",
            "• `/events <club or campus>` — upcoming for one group",
        ]
        if d:
            lines.append(f"• `/events {d}` — try this now")
        lines.append("• `/ask What events are happening for …?`")

    elif topic == "tri_state":
        lines += [
            "• `/compare_prices <search>` — cheapest listings + all seller links",
            "• `/tickets <category> [search] [budget]` — sports, concerts, comedy…",
            "• `/explore_events <interests>` — discover from what you're into",
            "• `/ask_tickets <question>` — conversational ticket help",
        ]
        if d:
            lines.append(f"• `/compare_prices {d}` — compare prices now")
            lines.append(f"• `/tickets all search:{d}` — ticket picks")

    elif topic == "date_ideas":
        lines += [
            "• `/date_ideas <vibe> [interests] [budget]` — curated plans + links",
            "• `/ask_date <question>` — ask about vibe, budget, logistics",
        ]
        if d:
            lines.append(f"• `/date_ideas any interests:{d}` — try this now")

    elif topic == "browse":
        lines += [
            "• `/whats_new` — this week's campus + tri-state highlights",
            "• `/ask <anything>` — general Rutgers advisor",
        ]

    else:  # coach
        lines += [
            "Use **`/find <goal>`** to open a private coach thread.",
            "The agent asks follow-ups and narrows to **one pick** (memory saved).",
            "Then chat in the thread or use `/continue <message>`.",
        ]

    lines.append("")
    lines.append(format_session_cta(topic, d))
    return "\n".join(lines)


def format_session_cta(topic: str, details: str = "") -> str:
    goal = build_find_goal(topic, details)
    return (
        "**Want a guided pick?** Start a coach session:\n"
        f"**`/find {goal[:120]}`** — thread chat, saved memory\n"
        "Or run **`/start`** again with **Start session: Yes**"
    )


def format_active_session_note(user_id: str) -> str:
    session = get_session(user_id)
    if not session:
        return ""
    return (
        f"\n\n💬 _Active coach session:_ **{session.goal[:80]}** — "
        f"`/continue` or your thread · `/session` for status"
    )


def append_next_steps(
    content: str,
    *,
    command: str,
    user_text: str = "",
    topic: str | None = None,
    user_id: str | None = None,
) -> str:
    """Append a short routing footer after command responses."""
    footer = _footer_for_command(command, user_text, topic=topic)
    if user_id:
        footer += format_active_session_note(user_id)
    if footer and footer not in content:
        return f"{content.rstrip()}\n\n{footer}"
    return content


def _footer_for_command(command: str, user_text: str, *, topic: str | None = None) -> str:
    text = (user_text or "").strip()
    domain = topic or detect_domain(text)

    if command in ("ask", "discover", "search", "events", "instagram"):
        if domain == "tri_state":
            return _tri_state_footer(text)
        if domain == "date":
            return _date_footer(text)
        if domain == "campus" or command in ("discover", "search", "instagram"):
            return _campus_clubs_footer(text)
        return _campus_mixed_footer(text)

    if command in ("tickets", "compare_prices", "explore_events", "ask_tickets"):
        return _tri_state_footer(text)

    if command in ("date_ideas", "ask_date"):
        return _date_footer(text)

    if command == "whats_new":
        return (
            "**Next steps**\n"
            "• `/compare_prices <artist or team>` — cheapest tri-state tickets\n"
            "• `/find one event from this list I should actually go to` — coach session\n"
            "• `/events <club>` — deep dive one campus group"
        )

    return ""


def _tri_state_footer(text: str) -> str:
    q = text[:80] if text else "concert NYC"
    goal = build_find_goal("tri_state", text)
    return (
        "**Next steps**\n"
        f"• `/compare_prices {q}` — sort by lowest listed price\n"
        f"• `/explore_events {text[:60] or 'your interests'}` — more ideas\n"
        f"• **`/find {goal[:100]}`** — coach thread to pick **one** show"
    )


def _date_footer(text: str) -> str:
    goal = build_find_goal("date_ideas", text)
    return (
        "**Next steps**\n"
        "• `/date_ideas <vibe> [interests] [budget]` — more curated ideas\n"
        "• `/ask_date <question>` — keep asking\n"
        f"• **`/find {goal[:100]}`** — coach picks **one** date plan for you"
    )


def _campus_clubs_footer(text: str) -> str:
    goal = build_find_goal("campus_clubs", text)
    return (
        "**Next steps**\n"
        f"• `/search {text[:60] or 'club name'}` — lookup one club\n"
        "• `/discover <major> <interests> <goals>` — broader recommendations\n"
        f"• **`/find {goal[:100]}`** — coach narrows to **one** club or event"
    )


def _campus_mixed_footer(text: str) -> str:
    goal = build_find_goal("campus_events", text)
    return (
        "**Next steps**\n"
        "• `/whats_new` — this week's events\n"
        f"• `/events {text[:60] or 'club name'}` — one group's calendar\n"
        f"• **`/find {goal[:100]}`** — coach picks **one** thing to do"
    )
