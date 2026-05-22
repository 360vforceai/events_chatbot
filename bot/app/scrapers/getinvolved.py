import time
import requests
from bs4 import BeautifulSoup
from app.db.client import get_supabase
from app.config import settings
from datetime import date

GETINVOLVED_BASE = "https://rutgers.campuslabs.com/engage"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEERBot/1.0)"}
CRAWL_DELAY = 2


def scrape_clubs() -> list[dict]:
    url = f"{GETINVOLVED_BASE}/organizations"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    BeautifulSoup(resp.text, "html.parser")
    time.sleep(CRAWL_DELAY)
    return []


def save_clubs_to_supabase(clubs: list[dict]):
    supabase = get_supabase()
    for club in clubs:
        club["last_updated"] = str(date.today())
        supabase.table("clubs").upsert(club).execute()


def run():
    clubs = scrape_clubs()
    save_clubs_to_supabase(clubs)
    print(f"[scraper] Saved {len(clubs)} clubs")


if __name__ == "__main__":
    run()
