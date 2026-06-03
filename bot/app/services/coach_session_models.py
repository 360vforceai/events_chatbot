"""Coach session data model (shared by service + store)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


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

    def seconds_idle(self) -> float:
        return time.time() - self.updated_at
