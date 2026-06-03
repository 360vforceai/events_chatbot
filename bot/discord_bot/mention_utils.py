"""Parse @mention messages for public-channel → thread coach flow."""

from __future__ import annotations

import re


def strip_bot_mention(content: str, bot_id: int) -> str:
    if not content:
        return ""
    cleaned = re.sub(rf"<@!?{bot_id}>", "", content)
    return " ".join(cleaned.split()).strip()


def goal_from_mention(content: str, bot_id: int) -> str:
    text = strip_bot_mention(content, bot_id)
    if not text:
        return "help me with Rutgers clubs, events, or tri-state plans"
    return text[:500]


def thread_name_for(username: str, goal: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", goal.split("\n")[0])[:40].strip() or "chat"
    slug = re.sub(r"\s+", "-", slug).lower()[:40] or "chat"
    base = f"{username}-{slug}"[:90]
    return base or "seer-chat"
