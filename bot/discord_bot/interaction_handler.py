import time
import logging
import discord
import asyncio
from discord.ext import tasks

from discord_bot.utils.rate_limiter import is_rate_limited, record_request, get_remaining_seconds
from discord_bot.utils.message_utils import split_message
from app.services.ai_client import get_response, get_router_decision
from app.services.memory_service import get_short_term_history, search_long_term_memories, save_memory_async
from app.services.events_client import (
    search_clubs, format_clubs_context,
    search_events, format_events_context
)

logger = logging.getLogger("discord_bot")

# Prevent Discord Gateway from replaying the same interaction
handled_interactions = {}

@tasks.loop(minutes=10)
async def purge_interactions():
    cutoff = time.time() - 600
    expired = [k for k, v in handled_interactions.items() if v < cutoff]
    for k in expired:
        del handled_interactions[k]

async def send_chunks(interaction: discord.Interaction, content: str):
    chunks = split_message(content)
    if not chunks:
        try:
            await interaction.edit_original_response(content="I could not generate a response. Please try again.")
        except Exception as e:
            logger.error(f"Edit reply failed: {e}")
        return
    
    try:
        await interaction.edit_original_response(content=chunks[0])
        for chunk in chunks[1:]:
            await interaction.followup.send(content=chunk)
    except Exception as e:
        logger.error(f"Follow-up failed: {e}")

async def run_advisor(user_id: str, username: str, question: str) -> str:
    # Step 1: get history, then let router decide which tables + keywords to use
    short_term_history = await get_short_term_history(user_id)
    decision = await get_router_decision(short_term_history, question)
    tables = decision.get("tables", [])
    keywords = decision.get("keywords", "")

    logger.info(f"Router decision applied userId={user_id} tables={tables} keywords={keywords}")

    # Step 2: concurrent searches across all relevant tables
    async def fetch_memories():
        if "community_memory" in tables:
            return await search_long_term_memories(keywords)
        return {"memories": [], "embedding": None}
        
    async def fetch_clubs():
        if "clubs" in tables:
            return await search_clubs(keywords)
        return []
        
    async def fetch_events():
        if "events" in tables:
            return await search_events(keywords)
        return []

    results = await asyncio.gather(
        fetch_memories(),
        fetch_clubs(),
        fetch_events()
    )
    
    memory_data, club_results, event_results = results
    memories = memory_data.get("memories", [])
    embedding = memory_data.get("embedding")

    # Step 3: format results into context strings
    rag_context = None
    if memories:
        rag_context = "\n".join([f'Discord user "@{m.get("metadata", {}).get("username", "unknown")}" previously said: "{m.get("content")}"' for m in memories])
        
    clubs_context = format_clubs_context(club_results)
    events_context = format_events_context(event_results)

    if rag_context: logger.info(f"RAG injected community memory count={len(memories)}")
    if clubs_context: logger.info(f"RAG injected clubs count={len(club_results)}")
    if events_context: logger.info(f"RAG injected events count={len(event_results)}")

    # Step 4: build message list and call the advisor
    messages = short_term_history + [{"role": "user", "content": question}]
    
    response_data = await get_response(messages, {
        "ragContext": rag_context,
        "clubsContext": clubs_context,
        "eventsContext": events_context,
        "keywords": keywords
    })
    content = response_data.get("content", "")

    # Save to short-term history in the background — don't block the reply
    asyncio.create_task(save_memory_async(user_id, username, question, content, embedding))

    return content

# /ask
async def handle_ask(interaction: discord.Interaction, user_id: str, username: str):
    question = getattr(interaction.namespace, "question", None)
    if not question:
        await interaction.followup.send("Please provide a question.", ephemeral=True)
        return

    content = await run_advisor(user_id, username, question)
    await send_chunks(interaction, content)
    logger.info(f"Handled /ask userId={user_id} username={username} questionLength={len(question)}")

# /discover (replaces /roadmap)
async def handle_discover(interaction: discord.Interaction, user_id: str, username: str):
    major = getattr(interaction.namespace, "major", "not specified")
    interests = getattr(interaction.namespace, "interests", "not specified")
    goals = getattr(interaction.namespace, "goals", "not specified")
    
    question = (
        f"Generate a personalized club and event recommendation for a Rutgers student. "
        f"Major: {major}. Interests: {interests}. Goals: {goals}. "
        f"Account for their major, interests, and suggest 3-5 relevant clubs."
    )

    content = await run_advisor(user_id, username, question)
    await send_chunks(interaction, content)
    logger.info(f"Handled /discover userId={user_id} username={username} major={major}")

# /search
async def handle_search(interaction: discord.Interaction, user_id: str, username: str):
    query = getattr(interaction.namespace, "query", None)
    if not query:
        await interaction.followup.send("Please provide a club or event name.", ephemeral=True)
        return

    question = (
        f"Look up the club or event \"{query}\". "
        f"Provide the full name, description, meeting times, and any upcoming events. "
    )

    content = await run_advisor(user_id, username, question)
    await send_chunks(interaction, content)
    logger.info(f"Handled /search userId={user_id} username={username} query={query}")

# /events (replaces /snipe)
async def handle_events(interaction: discord.Interaction, user_id: str, username: str):
    target = getattr(interaction.namespace, "target", None)
    if not target:
        await interaction.followup.send("Please provide a campus or club name.", ephemeral=True)
        return

    question = (
        f"Check upcoming events for \"{target}\". "
        f"List all upcoming events with their dates, times, locations, and if there is free food. "
    )

    content = await run_advisor(user_id, username, question)
    await send_chunks(interaction, content)
    logger.info(f"Handled /events userId={user_id} username={username} target={target}")

# /help
async def handle_help(interaction: discord.Interaction):
    help_text = (
        "**Rutgers S.E.E.R. Events Advisor — Commands**\n\n"
        "`/ask <question>` — Ask anything about clubs, events, or campus life.\n"
        "`/discover <major> <interests> <goals>` — Get personalized club recommendations.\n"
        "`/search <query>` — Look up a specific club or event.\n"
        "`/events <target>` — Check upcoming events for a campus or club.\n"
        "`/help` — Show this message.\n\n"
        "All advice is based on official Rutgers GetInvolved data."
    )

    try:
        await interaction.edit_original_response(content=help_text)
    except Exception as e:
        logger.error(f"Help reply failed: {e}")

    logger.info("Handled /help")

# Main dispatcher
async def handle_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.application_command:
        return

    command_name = interaction.command.name if interaction.command else None
    valid_commands = ['ask', 'discover', 'search', 'events', 'help']
    if command_name not in valid_commands:
        return

    user_id = str(interaction.user.id)
    username = interaction.user.name

    logger.info(f"Interaction received userId={user_id} command={command_name} id={interaction.id}")

    # Deduplication
    if interaction.id in handled_interactions:
        logger.warning(f"Duplicate interaction skipped id={interaction.id}")
        return
    handled_interactions[interaction.id] = time.time()

    # Rate limiting
    if is_rate_limited(user_id):
        remaining = get_remaining_seconds(user_id)
        try:
            await interaction.response.send_message(
                f"Please wait {remaining} second(s) before using another command.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Reply failed: {e}")
        return
    record_request(user_id)

    # Defer the reply
    try:
        await interaction.response.defer(thinking=True)
    except Exception as e:
        logger.error(f"Defer failed (interaction expired or already handled): {e}")
        return

    try:
        if command_name == 'ask':
            await handle_ask(interaction, user_id, username)
        elif command_name == 'discover':
            await handle_discover(interaction, user_id, username)
        elif command_name == 'search':
            await handle_search(interaction, user_id, username)
        elif command_name == 'events':
            await handle_events(interaction, user_id, username)
        elif command_name == 'help':
            await handle_help(interaction)
    except Exception as e:
        logger.error(f"Interaction handler error: {e}")
        try:
            await interaction.edit_original_response(content="Sorry, something went wrong. Please try again later.")
        except Exception as edit_err:
            logger.error(f"Fallback edit failed: {edit_err}")
