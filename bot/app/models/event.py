from pydantic import BaseModel
from typing import Optional


class Event(BaseModel):
    event_id: str
    club_id: str
    title: str
    date: str  # ISO format: YYYY-MM-DD
    time: str  # e.g. "6:00 PM"
    location: str
    campus: str
    type: str  # social | workshop | info_session | competition | fundraiser | showcase
    description: Optional[str] = None
    free_food: bool = False
    rsvp_link: Optional[str] = None
