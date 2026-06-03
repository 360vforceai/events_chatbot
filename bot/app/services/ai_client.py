import json
import logging
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger("discord_bot")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

def _get_client() -> tuple[AsyncOpenAI, str, str]:
    """
    Returns (client, fast_model, smart_model).
    Prefers OpenAI if OPENAI_API_KEY is set, falls back to Gemini.
    """
    if settings.openai_api_key:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        return client, "gpt-4o-mini", "gpt-4o"
    elif settings.gemini_api_key:
        client = AsyncOpenAI(
            api_key=settings.gemini_api_key,
            base_url=GEMINI_BASE_URL,
        )
        return client, "gemini-2.0-flash", "gemini-2.0-flash"
    else:
        raise RuntimeError("No AI API key configured. Set OPENAI_API_KEY or GEMINI_API_KEY.")


async def get_router_decision(history: list, question: str) -> dict:
    """
    Uses a fast model to extract keywords and decide which databases to search.
    """
    try:
        client, fast_model, _ = _get_client()
        system_prompt = """
        You are a routing assistant for a Rutgers University events bot.
        Based on the user's prompt, determine which databases need to be queried.
        Available tables: "clubs", "events", "community_memory".
        Extract the core search keywords (e.g., "computer science", "free food", "hackathon").

        Respond ONLY in JSON format:
        {"tables": ["events", "clubs"], "keywords": "search terms here"}
        """

        response = await client.chat.completions.create(
            model=fast_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Router error: {e}")
        return {"tables": ["events", "clubs"], "keywords": question}


async def get_response(messages: list, context: dict) -> dict:
    """
    Main LLM call that answers the user's question using retrieved context.
    """
    try:
        client, _, smart_model = _get_client()
        system_prompt = f"""
        You are S.E.E.R., the Rutgers AI Clubs & Events Advisor.
        Answer the user's question using ONLY the provided context. If the answer isn't in the context, say you don't know.

        CONTEXT:
        ---
        CLUBS:
        {context.get('clubsContext', 'None')}

        EVENTS:
        {context.get('eventsContext', 'None')}

        PAST MEMORIES:
        {context.get('ragContext', 'None')}
        ---
        """

        full_messages = [{"role": "system", "content": system_prompt}] + messages

        response = await client.chat.completions.create(
            model=smart_model,
            messages=full_messages,
            temperature=0.3
        )

        return {"content": response.choices[0].message.content}
    except Exception as e:
        logger.error(f"Advisor error: {e}")
        return {"content": "I am currently running in offline mode because the AI service is not configured. However, I did search the database for you!"}
