import time
import uuid
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.db.client import get_supabase

logger = logging.getLogger("discord_bot")

def get_headless_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # Need to have chromedriver installed or selenium manager will handle it
    driver = webdriver.Chrome(options=options)
    return driver

def scrape_rupa(driver) -> list:
    """Scrapes RUPA events."""
    events = []
    try:
        driver.get("https://rupa.rutgers.edu/events/")
        # Wait for events to load (adjust selector based on actual site structure)
        # This is a generic placeholder structure
        time.sleep(3) 
        
        # Example extraction (will need tuning based on actual DOM)
        # articles = driver.find_elements(By.CSS_SELECTOR, "article.event")
        # for article in articles:
        #     title = article.find_element(By.CSS_SELECTOR, ".entry-title").text
        #     events.append({ ... })
        
        logger.info("RUPA scraping completed (stub).")
    except Exception as e:
        logger.error(f"RUPA scraping failed: {e}")
    return events

def scrape_scarletknights(driver) -> list:
    """Scrapes ScarletKnights athletics events."""
    events = []
    try:
        driver.get("https://scarletknights.com/calendar")
        time.sleep(3)
        # Example extraction
        logger.info("ScarletKnights scraping completed (stub).")
    except Exception as e:
        logger.error(f"ScarletKnights scraping failed: {e}")
    return events

def scrape_rurec2go(driver) -> list:
    """Scrapes RURec2Go / IMLeagues events."""
    events = []
    try:
        # Note: IMLeagues often requires login or complex navigation
        driver.get("https://services.rec.rutgers.edu/")
        time.sleep(3)
        # Example extraction
        logger.info("RURec2Go scraping completed (stub).")
    except Exception as e:
        logger.error(f"RURec2Go scraping failed: {e}")
    return events

def save_events_to_supabase(events: list[dict]):
    if not events:
        return
    try:
        supabase = get_supabase()
        for event in events:
            supabase.table("events").upsert(event).execute()
        logger.info(f"Saved {len(events)} headless events to Supabase.")
    except Exception as e:
        logger.error(f"Failed to save headless events: {e}")

def run_headless_scrapers():
    driver = None
    all_events = []
    try:
        driver = get_headless_driver()
        all_events.extend(scrape_rupa(driver))
        all_events.extend(scrape_scarletknights(driver))
        all_events.extend(scrape_rurec2go(driver))
        
        save_events_to_supabase(all_events)
    except Exception as e:
        logger.error(f"Headless scraper runner failed: {e}")
    finally:
        if driver:
            driver.quit()
            
    return len(all_events)

if __name__ == "__main__":
    run_headless_scrapers()
