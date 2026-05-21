import logging

logger = logging.getLogger("discord_bot")

async def get_router_decision(history: list, question: str) -> dict:
    # Stub implementation
    return {
        "tables": ["clubs", "events"],
        "keywords": question
    }

async def get_response(messages: list, context: dict) -> dict:
    # Stub implementation
    return {
        "content": f"This is a stub AI response for: {messages[-1]['content']}"
    }
