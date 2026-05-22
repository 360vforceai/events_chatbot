from fastapi import FastAPI
from app.routers import clubs, events, users, scraper, recommend

app = FastAPI(title="SEER API", version="1.0.0")

app.include_router(clubs.router, prefix="/clubs", tags=["clubs"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(recommend.router, prefix="/recommend", tags=["recommend"])
app.include_router(scraper.router, prefix="/scrape", tags=["scraper"])


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
