from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.db.client import get_supabase
from app.models.event import Event
from app.config import settings

router = APIRouter()


class EventSearchRequest(BaseModel):
    keyword: Optional[str] = None
    campus: Optional[str] = None
    event_type: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    free_food: Optional[bool] = None


@router.post("/search", response_model=list[Event])
def search_events(req: EventSearchRequest):
    supabase = get_supabase()
    query = supabase.table("events").select("*")
    
    if req.campus:
        query = query.eq("campus", req.campus)
    if req.free_food is not None:
        query = query.eq("free_food", req.free_food)
    if req.keyword:
        kw = req.keyword.lower()
        query = query.or_(f"title.ilike.%{kw}%,description.ilike.%{kw}%")
        
    response = query.execute()
    return response.data


@router.get("/{event_id}", response_model=Event)
def get_event(event_id: str):
    supabase = get_supabase()
    response = supabase.table("events").select("*").eq("event_id", event_id).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Event not found")
    return response.data[0]
