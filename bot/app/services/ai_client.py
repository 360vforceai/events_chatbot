import json
import logging
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger("discord_bot")

async def get_router_decision(history: list, question: str) -> dict:
    """
    Uses a fast/cheap model to extract keywords and decide which databases to search.
    """
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        system_prompt = """
        You are a routing assistant for a Rutgers University events bot.
        Based on the user's prompt, determine which databases need to be queried.
        Available tables: "clubs", "events", "community_memory".
        Extract the core search keywords (e.g., "computer science", "free food", "hackathon").
        
        Respond ONLY in JSON format:
        {"tables": ["events", "clubs"], "keywords": "search terms here"}
        """
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini", # Use a fast model for routing
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Router error (OpenAI might not be configured): {e}")
        # Fallback if OpenAI fails or keys aren't set
        return {"tables": ["events", "clubs"], "keywords": question}

async def get_response(messages: list, context: dict) -> dict:
    """
    The main LLM call that answers the user's question using the retrieved context.
    """
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
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
        
        # Prepend the system prompt to the conversation history
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = await client.chat.completions.create(
            model="gpt-4o", # Use the smarter model for the final answer
            messages=full_messages,
            temperature=0.3
        )
        
        return {"content": response.choices[0].message.content}
    except Exception as e:
        logger.error(f"Advisor error (OpenAI might not be configured): {e}")
        # Fallback if OpenAI fails or keys aren't set
        return {"content": "I am currently running in offline mode because OpenAI keys are not configured. However, I did search the database for you!"}