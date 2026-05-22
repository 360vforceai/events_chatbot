from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.db.client import get_supabase
from app.services.recommender import get_recommendations

router = APIRouter()


class RecommendRequest(BaseModel):
    major: Optional[str] = None
    interests: Optional[str | list[str]] = None
    goals: Optional[str] = None
    campus: Optional[str] = None
    time_commitment: Optional[str] = None


@router.post("/")
def recommend(req: RecommendRequest):
    try:
        supabase = get_supabase()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    response = supabase.table("clubs").select("*").limit(50).execute()
    clubs = response.data or []

    profile = req.model_dump()
    if isinstance(profile.get("interests"), list):
        profile["interests"] = ", ".join(profile["interests"])

    recommendations = get_recommendations(profile, clubs)
    club_by_id = {c["club_id"]: c for c in clubs if c.get("club_id")}

    for rec in recommendations:
        rec["club"] = club_by_id.get(rec.get("club_id"))

    return recommendations
