"""Persist coach sessions to Supabase (survives bot restarts)."""

from __future__ import annotations

import logging
import time

from app.db.client import get_supabase
from app.services.coach_session_models import CoachSession

logger = logging.getLogger("discord_bot")


def _session_to_row(session: CoachSession, *, ended_reason: str | None = None) -> dict:
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "username": session.username,
        "goal": session.goal,
        "domain": session.domain,
        "thread_id": session.thread_id,
        "channel_id": session.channel_id,
        "status": session.status,
        "ended_reason": ended_reason,
        "turn_count": session.turn_count,
        "messages": session.messages,
        "created_at": int(session.created_at),
        "updated_at": int(session.updated_at),
    }


def _row_to_session(row: dict) -> CoachSession:
    return CoachSession(
        session_id=row["session_id"],
        user_id=row["user_id"],
        username=row.get("username") or "",
        goal=row["goal"],
        domain=row.get("domain") or "general",
        thread_id=row.get("thread_id"),
        channel_id=row.get("channel_id"),
        messages=row.get("messages") or [],
        status=row.get("status") or "active",
        turn_count=row.get("turn_count") or 0,
        created_at=float(row.get("created_at") or time.time()),
        updated_at=float(row.get("updated_at") or time.time()),
    )


def save_session(session: CoachSession, *, ended_reason: str | None = None) -> bool:
    try:
        supabase = get_supabase()
        supabase.table("coach_sessions").upsert(_session_to_row(session, ended_reason=ended_reason)).execute()
        return True
    except Exception as e:
        logger.error("coach_sessions save failed: %s", e)
        return False


def fetch_active_session(user_id: str) -> CoachSession | None:
    try:
        supabase = get_supabase()
        rows = (
            supabase.table("coach_sessions")
            .select("*")
            .eq("user_id", user_id)
            .in_("status", ["active", "resolved"])
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        return _row_to_session(rows[0]) if rows else None
    except Exception as e:
        logger.error("coach_sessions fetch active failed: %s", e)
        return None


def fetch_session_by_thread(thread_id: int) -> CoachSession | None:
    try:
        supabase = get_supabase()
        rows = (
            supabase.table("coach_sessions")
            .select("*")
            .eq("thread_id", thread_id)
            .in_("status", ["active", "resolved"])
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        return _row_to_session(rows[0]) if rows else None
    except Exception as e:
        logger.error("coach_sessions fetch thread failed: %s", e)
        return None


def fetch_resumable_session(user_id: str, max_age_seconds: int) -> CoachSession | None:
    """Last idle-ended session the student can pick up with /continue."""
    try:
        supabase = get_supabase()
        cutoff = int(time.time()) - max_age_seconds
        rows = (
            supabase.table("coach_sessions")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "ended")
            .eq("ended_reason", "idle")
            .gte("updated_at", cutoff)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        return _row_to_session(rows[0]) if rows else None
    except Exception as e:
        logger.error("coach_sessions fetch resumable failed: %s", e)
        return None


def fetch_idle_candidates(idle_seconds: int) -> list[CoachSession]:
    """Active sessions with no message in idle_seconds."""
    try:
        supabase = get_supabase()
        cutoff = int(time.time()) - idle_seconds
        rows = (
            supabase.table("coach_sessions")
            .select("*")
            .in_("status", ["active", "resolved"])
            .lt("updated_at", cutoff)
            .execute()
            .data
            or []
        )
        return [_row_to_session(r) for r in rows]
    except Exception as e:
        logger.error("coach_sessions fetch idle failed: %s", e)
        return []
