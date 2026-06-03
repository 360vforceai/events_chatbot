"""Coach sessions — persistent memory, 15-minute idle timeout, resume via /continue."""

from __future__ import annotations

import time
import uuid

from app.config import settings
from app.services import coach_session_store
from app.services.coach_session_models import CoachSession

SESSION_TTL_SECONDS = 60 * 60 * 24  # keep history 24h for resume
MAX_TURNS = 24


def idle_seconds() -> int:
    return max(60, settings.coach_session_idle_minutes * 60)


_sessions_by_user: dict[str, CoachSession] = {}
_sessions_by_thread: dict[int, str] = {}


def _hydrate(session: CoachSession):
    _sessions_by_user[session.user_id] = session
    if session.thread_id:
        _sessions_by_thread[session.thread_id] = session.user_id


def _unindex(session: CoachSession):
    _sessions_by_user.pop(session.user_id, None)
    if session.thread_id:
        _sessions_by_thread.pop(session.thread_id, None)


def _persist(session: CoachSession, *, ended_reason: str | None = None):
    coach_session_store.save_session(session, ended_reason=ended_reason)


def is_idle_expired(session: CoachSession) -> bool:
    return session.status in ("active", "resolved") and session.seconds_idle() >= idle_seconds()


def detect_domain(goal: str) -> str:
    g = f" {goal.lower()} "
    if any(w in g for w in ("date", "first date", "romantic", "partner", "coffee date")):
        return "date"
    if any(
        w in g
        for w in (
            "ticket",
            "concert",
            "sports",
            "game",
            "show",
            "comedy",
            "theater",
            "broadway",
            "festival",
            "msg",
            "nyc",
            "tri-state",
            "nba",
            "nfl",
        )
    ):
        return "tri_state"
    if any(w in g for w in ("club", "organization", "major", "getinvolved", "campus life")):
        return "campus"
    return "general"


def start_session(
    *,
    user_id: str,
    username: str,
    goal: str,
    thread_id: int | None = None,
    channel_id: int | None = None,
) -> CoachSession:
    existing = get_session(user_id)
    if existing:
        end_session(user_id, reason="replaced")

    session = CoachSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        username=username,
        goal=goal.strip(),
        domain=detect_domain(goal),
        thread_id=thread_id,
        channel_id=channel_id,
    )
    _hydrate(session)
    _persist(session)
    return session


def attach_thread(user_id: str, thread_id: int, channel_id: int | None = None):
    session = _sessions_by_user.get(user_id) or coach_session_store.fetch_active_session(user_id)
    if not session:
        return None
    if session.thread_id:
        _sessions_by_thread.pop(session.thread_id, None)
    session.thread_id = thread_id
    session.channel_id = channel_id
    _hydrate(session)
    _persist(session)
    return session


def _load_session(user_id: str) -> CoachSession | None:
    session = _sessions_by_user.get(user_id)
    if session:
        return session
    session = coach_session_store.fetch_active_session(user_id)
    if session:
        _hydrate(session)
    return session


def get_session(user_id: str) -> CoachSession | None:
    session = _load_session(user_id)
    if not session:
        return None
    if is_idle_expired(session):
        end_session(user_id, reason="idle")
        return None
    return session


def get_session_by_thread(thread_id: int) -> CoachSession | None:
    user_id = _sessions_by_thread.get(thread_id)
    session = _sessions_by_user.get(user_id) if user_id else None
    if not session:
        session = coach_session_store.fetch_session_by_thread(thread_id)
        if session:
            _hydrate(session)
    if not session:
        return None
    if is_idle_expired(session):
        end_session(session.user_id, reason="idle")
        return None
    return session


def resume_session(user_id: str) -> CoachSession | None:
    """Re-open an idle-ended session so /continue picks up where they left off."""
    session = coach_session_store.fetch_resumable_session(user_id, SESSION_TTL_SECONDS)
    if not session:
        return None
    session.status = "active"
    session.touch()
    _hydrate(session)
    _persist(session)
    return session


def end_session(user_id: str, *, reason: str = "user") -> CoachSession | None:
    session = _sessions_by_user.get(user_id) or coach_session_store.fetch_active_session(user_id)
    if not session:
        resumable = coach_session_store.fetch_resumable_session(user_id, SESSION_TTL_SECONDS)
        if resumable and reason == "user":
            session = resumable
        else:
            return None
    session.status = "ended"
    session.touch()
    _unindex(session)
    _persist(session, ended_reason=reason)
    return session


def mark_resolved(user_id: str):
    session = get_session(user_id) or _load_session(user_id)
    if session:
        session.status = "resolved"
        session.touch()
        _persist(session)


def save_turn(session: CoachSession):
    _persist(session)


def session_status_text(session: CoachSession) -> str:
    idle_mins = settings.coach_session_idle_minutes
    age_min = int(session.seconds_idle() / 60)
    remaining = max(0, idle_mins - age_min)
    thread_note = f"Thread: <#{session.thread_id}>" if session.thread_id else "Use `/continue <message>`"
    return (
        f"**Coach session** — _{session.status}_ (memory saved)\n"
        f"**Goal:** {session.goal}\n"
        f"**Focus:** {session.domain.replace('_', ' ')}\n"
        f"**Turns:** {session.turn_count}/{MAX_TURNS}\n"
        f"**Idle timeout:** {remaining} min left (auto-ends after {idle_mins} min quiet)\n"
        f"{thread_note}\n\n"
        "Chat in your thread or `/continue`. `/end_session` to close."
    )


def collect_idle_sessions() -> list[CoachSession]:
    """Sessions to close due to inactivity (memory + Supabase)."""
    idle = idle_seconds()
    out: list[CoachSession] = []
    seen: set[str] = set()

    for session in list(_sessions_by_user.values()):
        if session.user_id in seen:
            continue
        if session.status in ("active", "resolved") and session.seconds_idle() >= idle:
            out.append(session)
            seen.add(session.user_id)

    for session in coach_session_store.fetch_idle_candidates(idle):
        if session.user_id not in seen:
            out.append(session)
            seen.add(session.user_id)

    return out
