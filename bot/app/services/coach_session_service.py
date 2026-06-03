"""In-memory coach sessions — multi-turn agent chats that narrow to one pick."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

SESSION_TTL_SECONDS = 60 * 60 * 24  # 24 hours
MAX_TURNS = 24


@dataclass
class CoachSession:
    session_id: str
    user_id: str
    username: str
    goal: str
    domain: str
    thread_id: int | None = None
    channel_id: int | None = None
    messages: list[dict] = field(default_factory=list)
    status: str = "active"  # active | resolved | ended
    turn_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def touch(self):
        self.updated_at = time.time()

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if role == "user":
            self.turn_count += 1
        self.touch()

    def history_for_ai(self) -> list[dict]:
        return list(self.messages)


_sessions_by_user: dict[str, CoachSession] = {}
_sessions_by_thread: dict[int, str] = {}


def _purge_stale():
    cutoff = time.time() - SESSION_TTL_SECONDS
    stale_users = [
        uid
        for uid, s in _sessions_by_user.items()
        if s.updated_at < cutoff or s.status == "ended"
    ]
    for uid in stale_users:
        session = _sessions_by_user.pop(uid, None)
        if session and session.thread_id:
            _sessions_by_thread.pop(session.thread_id, None)


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
    _purge_stale()
    existing = _sessions_by_user.get(user_id)
    if existing:
        end_session(user_id)

    session = CoachSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        username=username,
        goal=goal.strip(),
        domain=detect_domain(goal),
        thread_id=thread_id,
        channel_id=channel_id,
    )
    _sessions_by_user[user_id] = session
    if thread_id:
        _sessions_by_thread[thread_id] = user_id
    return session


def attach_thread(user_id: str, thread_id: int, channel_id: int | None = None):
    session = _sessions_by_user.get(user_id)
    if not session:
        return None
    if session.thread_id:
        _sessions_by_thread.pop(session.thread_id, None)
    session.thread_id = thread_id
    session.channel_id = channel_id
    _sessions_by_thread[thread_id] = user_id
    session.touch()
    return session


def get_session(user_id: str) -> CoachSession | None:
    _purge_stale()
    return _sessions_by_user.get(user_id)


def get_session_by_thread(thread_id: int) -> CoachSession | None:
    _purge_stale()
    user_id = _sessions_by_thread.get(thread_id)
    if not user_id:
        return None
    return _sessions_by_user.get(user_id)


def end_session(user_id: str) -> CoachSession | None:
    session = _sessions_by_user.pop(user_id, None)
    if session and session.thread_id:
        _sessions_by_thread.pop(session.thread_id, None)
    if session:
        session.status = "ended"
    return session


def mark_resolved(user_id: str):
    session = _sessions_by_user.get(user_id)
    if session:
        session.status = "resolved"
        session.touch()


def session_status_text(session: CoachSession) -> str:
    age_min = int((time.time() - session.updated_at) / 60)
    thread_note = f"Thread: <#{session.thread_id}>" if session.thread_id else "No thread — use `/continue`"
    return (
        f"**Coach session** — _{session.status}_\n"
        f"**Goal:** {session.goal}\n"
        f"**Focus:** {session.domain.replace('_', ' ')}\n"
        f"**Turns:** {session.turn_count}/{MAX_TURNS}\n"
        f"**Last active:** {age_min} min ago\n"
        f"{thread_note}\n\n"
        "Keep chatting in your thread, or use `/continue <message>`. "
        "Use `/end_session` when you're done."
    )
