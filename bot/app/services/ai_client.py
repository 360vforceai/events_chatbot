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

        Rules:
        - If the user asks about clubs, majors, organizations, CS/computer science, STEM, hobbies,
          or recommendations, ALWAYS include "clubs" in tables.
        - Rutgers has hundreds of student organizations; use broad keywords (e.g. "computer science"
          not just "CS") so search can return many matches.
        - Extract core search keywords (e.g. "computer science", "free food", "hackathon").

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
        Rutgers has hundreds of registered student organizations on getINVOLVED. Use the CLUBS context
        as the authoritative list for this answer — list every matching club shown there by name.
        Do NOT claim Rutgers only has a few clubs in a category if the context lists many.
        If the user asks for clubs in a field (e.g. computer science) and multiple clubs appear in
        context, enumerate them (name + one-line why it fits). Mention Instagram/getINVOLVED links when present.
        If something is not in the context, say so — but do not invent club names.

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


async def get_tri_state_recommendations(
    *,
    mode: str,
    category: str,
    interests: str,
    search: str,
    budget: str,
    rutgers_events_context: str,
    search_query: str,
) -> dict:
    """
    Structured tri-state event + ticket guidance for /tickets and /explore_events.
    Each pick includes search_query for purchase-link generation.
    """
    client, _, smart_model = _get_client()
    budget_note = f"Student budget: {budget}." if budget else "Assume student budget — favor cheaper sections and resale deals."

    system_prompt = f"""
    You are S.E.E.R.'s tri-state event scout for Rutgers students (NY, NJ, PA).
    {budget_note}
    Mode: {mode} (tickets = find affordable tickets; explore = match interests to events).

    Real venues/teams to draw from: Rutgers Athletic Center, SHI Stadium, Prudential Center (Newark),
    MetLife Stadium, Madison Square Garden, Barclays Center, Yankee Stadium, Citi Field, Lincoln Center,
    Radio City, Bowery Ballroom, Irving Plaza, Wells Fargo Center (Philly), Atlantic City boards.

    Rules:
    - Suggest realistic events a student could attend from New Brunswick NJ (train/bus/car).
    - Each pick MUST include a specific search_query string we will pass to ticket sites (artist+venue or team+city).
    - Include price_tip (upper deck, weeknight, Gametime/SeatGeek, rush tickets, etc.).
    - Do not invent exact prices or dates; use timing like "this month", "weekends", "check schedule".
    - If rutgers campus events are provided, mention 1-2 only when relevant (free/cheap).

    Rutgers campus events context:
    {rutgers_events_context or "None"}

    Respond ONLY JSON:
    {{
      "intro": "1-2 sentence overview",
      "picks": [
        {{
          "title": "Event or scene name",
          "event_type": "sports|concert|comedy|theater|festival",
          "venue": "Venue name",
          "area": "City, State",
          "timing": "When to look",
          "price_tip": "How to save money",
          "search_query": "exact ticket search phrase"
        }}
      ],
      "money_saving_tips": ["tip1", "tip2"]
    }}
    Provide 4-6 picks for explore mode, 3-5 for tickets mode.
    Category focus: {category}. User search: {search or "none"}. Interests: {interests or "none"}.
    Base ticket search phrase: {search_query}
    """

    user_content = (
        f"Find tri-state events and cheap ticket strategies. "
        f"Category: {category}. Search: {search}. Interests: {interests}."
    )

    response = await client.chat.completions.create(
        model=smart_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.4,
    )
    return json.loads(response.choices[0].message.content)


async def get_tri_state_ask_response(history: list, question: str) -> dict:
    """Conversational tri-state Q&A — helps students explore show and ticket interests."""
    client, _, smart_model = _get_client()
    system_prompt = """
    You are S.E.E.R.'s tri-state culture coach for Rutgers students (NY, NJ, PA).
    Help the student develop whatever interests they mention — genres, teams, venues, or local scenes.
    Be encouraging and specific. Suggest ways to explore cheaply (weeknights, upper decks, SeatGeek/Gametime).

    When relevant, include ticket picks with search_query for purchase links.
    Venues: MSG, Barclays, Prudential, MetLife, Rutgers Athletic Center, Bowery Ballroom, NYC/NJ comedy clubs.

    Respond ONLY JSON:
    {
      "answer": "2-4 paragraphs answering their question and nurturing their interests",
      "picks": [
        {
          "title": "...",
          "venue": "...",
          "area": "...",
          "timing": "...",
          "price_tip": "...",
          "search_query": "ticket search phrase"
        }
      ],
      "follow_up_ideas": ["short idea they could explore next"],
      "money_saving_tips": ["tip1"]
    }
    Include 0-4 picks only when tickets/events fit the question.
    """
    messages = [{"role": "system", "content": system_prompt}] + history + [
        {"role": "user", "content": question}
    ]
    response = await client.chat.completions.create(
        model=smart_model,
        response_format={"type": "json_object"},
        messages=messages,
        temperature=0.5,
    )
    return json.loads(response.choices[0].message.content)


async def get_date_planning_response(
    *,
    mode: str,
    question: str,
    history: list,
    vibe: str,
    budget: str,
    interests: str,
) -> dict:
    """First-date planning: Q&A (ask) or curated discovery."""
    client, _, smart_model = _get_client()
    budget_note = f"Budget: {budget}." if budget else "Assume college-student budget — affordable, low-pressure."

    system_prompt = f"""
    You are S.E.E.R.'s first-date planner for Rutgers students near New Brunswick, NJ.
    {budget_note}
    Mode: {mode} (ask = answer their question; discover = suggest date ideas from vibe/interests).

    Areas: New Brunswick (George St, Easton Ave, campus), Highland Park, Princeton, Newark,
    Jersey City, NYC (PATH/NJ Transit), Philadelphia day trips.
    Favor comfortable, public, low-pressure first dates. Brief safety/comfort notes when helpful.

    Respond ONLY JSON:
    {{
      "answer": "ask: 2-3 paragraphs. discover: 1-2 sentence intro.",
      "ideas": [
        {{
          "title": "Date idea name",
          "description": "What to do and why it works for a first date",
          "area": "Neighborhood or city",
          "timing": "Best time",
          "estimated_cost": "e.g. $15-30 each",
          "search_query": "phrase for maps or restaurant search"
        }}
      ],
      "etiquette_tips": ["tip1"],
      "follow_up_ideas": ["optional next step"]
    }}
    Discover: 5-7 ideas. Ask: 3-5 ideas only if they illustrate your answer.
    Vibe: {vibe or "not specified"}. Interests: {interests or "not specified"}.
    """

    if mode == "ask":
        messages = [{"role": "system", "content": system_prompt}] + history + [
            {"role": "user", "content": question}
        ]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Suggest first date ideas. Vibe: {vibe}. Interests: {interests}.",
            },
        ]

    response = await client.chat.completions.create(
        model=smart_model,
        response_format={"type": "json_object"},
        messages=messages,
        temperature=0.5,
    )
    return json.loads(response.choices[0].message.content)
