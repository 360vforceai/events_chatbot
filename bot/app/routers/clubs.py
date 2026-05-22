from fastapi import APIRouter, HTTPException
from app.db.client import get_supabase
from app.models.club import Club
from app.config import settings

router = APIRouter()


@router.get("/{club_id}", response_model=Club)
def get_club(club_id: str):
    supabase = get_supabase()
    response = supabase.table("clubs").select("*").eq("club_id", club_id).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Club not found")
    return response.data[0]


@router.get("/", response_model=list[Club])
def list_clubs(campus: str = None, category: str = None):
    supabase = get_supabase()
    query = supabase.table("clubs").select("*")
    
    if campus:
        query = query.eq("campus", campus)
        
    response = query.execute()
    return response.data
