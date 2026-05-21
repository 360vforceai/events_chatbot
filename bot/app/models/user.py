from pydantic import BaseModel
from typing import Optional


class UserPreferences(BaseModel):
    discord_user_id: str
    major: Optional[str] = None
    interests: list[str] = []
    preferred_campus: Optional[str] = None
    subscriptions: list[str] = []  # club_id or "category:<name>"
    digest_enabled: bool = True
