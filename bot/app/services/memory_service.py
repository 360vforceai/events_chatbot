import logging
from app.db.client import get_supabase
from app.config import settings
import time
import uuid

logger = logging.getLogger("discord_bot")

async def get_short_term_history(user_id: str) -> list:
    """Fetch the last 5 messages from this user to maintain conversation context."""
    supabase = get_supabase()
    
    response = (
        supabase.table("interactions")
        .select("*")
        .eq("user_id", user_id)
        .order("timestamp", desc=True)
        .limit(2)
        .execute()
    )
    
    items = response.data
    
    history = []
    for item in reversed(items):
        history.append({"role": "user", "content": item.get("query")})
        history.append({"role": "assistant", "content": item.get("response")})
        
    return history

async def save_memory_async(user_id: str, username: str, question: str, content: str, embedding=None):
    """Saves the interaction to Supabase."""
    supabase = get_supabase()
    
    supabase.table("interactions").insert({
        "interaction_id": str(uuid.uuid4()),
        "user_id": user_id,
        "username": username,
        "query": question,
        "response": content,
        "timestamp": int(time.time())
    }).execute()
    
    logger.info(f"Saved memory for {username}")