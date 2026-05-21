from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.db.client import get_dynamodb
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
    db = get_dynamodb()
    table = db.Table(settings.dynamodb_table_events)
    # TODO: replace scan with GSI query in Phase 2
    result = table.scan()
    items = result.get("Items", [])
    if req.campus:
        items = [i for i in items if i.get("campus") == req.campus]
    if req.free_food is not None:
        items = [i for i in items if i.get("free_food") == req.free_food]
    if req.keyword:
        kw = req.keyword.lower()
        items = [
            i
            for i in items
            if kw in i.get("title", "").lower() or kw in i.get("description", "").lower()
        ]
    return items


@router.get("/{event_id}", response_model=Event)
def get_event(event_id: str):
    db = get_dynamodb()
    table = db.Table(settings.dynamodb_table_events)
    result = table.get_item(Key={"event_id": event_id})
    if "Item" not in result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result["Item"]
