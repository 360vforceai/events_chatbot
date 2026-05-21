from fastapi import APIRouter, HTTPException
from app.db.client import get_dynamodb
from app.models.club import Club
from app.config import settings

router = APIRouter()


@router.get("/{club_id}", response_model=Club)
def get_club(club_id: str):
    db = get_dynamodb()
    table = db.Table(settings.dynamodb_table_clubs)
    result = table.get_item(Key={"club_id": club_id})
    if "Item" not in result:
        raise HTTPException(status_code=404, detail="Club not found")
    return result["Item"]


@router.get("/", response_model=list[Club])
def list_clubs(campus: str = None, category: str = None):
    db = get_dynamodb()
    table = db.Table(settings.dynamodb_table_clubs)
    # TODO: add GSI filtering by campus / category in Phase 2
    result = table.scan()
    items = result.get("Items", [])
    if campus:
        items = [i for i in items if i.get("campus") == campus]
    return items
