from fastapi import APIRouter, HTTPException, Depends, Header
from app.scrapers import getinvolved, calendar, headless
from app.config import settings
import logging

logger = logging.getLogger("discord_bot")
router = APIRouter()

# Simple dependency to check the admin API key
def verify_admin_key(x_admin_key: str = Header(...)):
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin API key")
    return x_admin_key

@router.post("/trigger/getinvolved")
def trigger_getinvolved_scraper(admin_key: str = Depends(verify_admin_key)):
    """Triggers the GetInvolved API scraper."""
    try:
        count = getinvolved.run()
        return {"status": "success", "message": f"GetInvolved scraper executed, saved {count} events"}
    except Exception as e:
        logger.error(f"Scraper error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trigger/calendar")
def trigger_calendar_scraper(admin_key: str = Depends(verify_admin_key)):
    """Triggers the Rutgers RSS Calendar scraper."""
    try:
        count = calendar.run_calendar_scraper()
        return {"status": "success", "message": f"Calendar scraper executed, saved {count} events"}
    except Exception as e:
        logger.error(f"Scraper error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trigger/headless")
def trigger_headless_scraper(admin_key: str = Depends(verify_admin_key)):
    """Triggers the Headless (Selenium) scrapers for RUPA, ScarletKnights, RURec2Go."""
    try:
        count = headless.run_headless_scrapers()
        return {"status": "success", "message": f"Headless scrapers executed, saved {count} events"}
    except Exception as e:
        logger.error(f"Scraper error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
