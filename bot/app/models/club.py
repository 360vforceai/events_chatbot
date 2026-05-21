from pydantic import BaseModel
from typing import Optional
from datetime import date


class ClubLinks(BaseModel):
    instagram: Optional[str] = None
    website: Optional[str] = None
    getinvolved: Optional[str] = None


class Club(BaseModel):
    club_id: str
    name: str
    description: str
    category: list[str]
    campus: str
    meeting_time: Optional[str] = None
    links: ClubLinks = ClubLinks()
    tags: list[str] = []
    last_updated: Optional[date] = None
