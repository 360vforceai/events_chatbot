from fastapi import APIRouter, HTTPException
from datetime import date

from app.db.client import get_supabase
from app.models.user import UserPreferences

router = APIRouter()


def _get_supabase():
    try:
        return get_supabase()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get("/{discord_user_id}", response_model=UserPreferences)
def get_preferences(discord_user_id: str):
    supabase = _get_supabase()
    response = (
        supabase.table("users")
        .select("*")
        .eq("discord_user_id", discord_user_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return UserPreferences(discord_user_id=discord_user_id)
    return response.data[0]


@router.post("/preferences", response_model=UserPreferences)
def save_preferences(prefs: UserPreferences):
    supabase = _get_supabase()
    item = prefs.model_dump()
    supabase.table("users").upsert(item, on_conflict="discord_user_id").execute()
    return prefs


@router.get("/{discord_user_id}/digest")
def get_digest(discord_user_id: str):
    supabase = _get_supabase()
    user_resp = (
        supabase.table("users")
        .select("*")
        .eq("discord_user_id", discord_user_id)
        .limit(1)
        .execute()
    )
    subscriptions = []
    if user_resp.data:
        subscriptions = user_resp.data[0].get("subscriptions") or []

    events_resp = supabase.table("events").select("*").execute()
    events = events_resp.data or []
    today = date.today().isoformat()
    events = [e for e in events if (e.get("date") or "") >= today]

    if subscriptions:
        events = [
            e
            for e in events
            if e.get("club_id") in subscriptions
            or e.get("campus") in subscriptions
            or e.get("type") in subscriptions
        ]

    return events[:20]
