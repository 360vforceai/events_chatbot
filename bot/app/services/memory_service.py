import logging

logger = logging.getLogger("discord_bot")

async def get_short_term_history(user_id: str) -> list:
    return []

async def search_long_term_memories(keywords: str) -> dict:
    return {"memories": [], "embedding": None}

async def save_memory_async(user_id: str, username: str, question: str, content: str, embedding=None):
    logger.info(f"Saved memory for {username}")
