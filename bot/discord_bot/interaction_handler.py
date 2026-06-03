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
    search_clubs,
    format_clubs_context,
    search_events,
    format_events_context,
    find_club_by_name,
    format_instagram_message,
    format_whats_new,
    merge_campus_whats_new,
)
from app.services import live_events_cache
from app.services.club_search import expand_search_terms
from app.services.ticket_service import (
    find_cheap_tickets,
    explore_events_by_interests,
    ask_tri_state_question,
    compare_ticket_prices,
)
from app.services.date_ideas_service import ask_about_first_dates, discover_first_date_ideas
from app.services.command_guide import append_next_steps, build_find_goal, format_topic_guide
from discord_bot.coach_handler import (
    handle_continue,
    handle_end_session,
    handle_find,
    handle_session_status,
)

logger = logging.getLogger("discord_bot")

_CLUB_QUESTION_HINTS = (
    "club", "clubs", "organization", "organizations", "org", "orgs",
    "computer science", "computer", " cs ", "cs,", "informatics",
    "major", "recommend", "usacs", "rumad", "stem", "greek", "honor society",
)


def _question_implies_clubs(question: str) -> bool:
    q = f" {question.lower()} "
    return any(h in q for h in _CLUB_QUESTION_HINTS)


def _slash_choice_value(value) -> str | None:
    """Normalize discord.py Choice parameters to plain strings."""
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


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


async def send_with_guide(
    interaction: discord.Interaction,
    content: str,
    *,
    command: str,
    user_text: str = "",
    user_id: str = "",
    topic: str | None = None,
):
    """Send response plus next-step command routing."""
    enriched = append_next_steps(
        content,
        command=command,
        user_text=user_text,
        topic=topic,
        user_id=user_id or None,
    )
    await send_chunks(interaction, enriched)

async def run_advisor(user_id: str, username: str, question: str, extra_clubs_search: str = "") -> str:
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
        search_term = extra_clubs_search or keywords
        if not search_term and _question_implies_clubs(question):
            search_term = keywords or question
        if search_term or "clubs" in tables:
            return await search_clubs(search_term or question)
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
    await send_with_guide(
        interaction, content, command="ask", user_text=question, user_id=user_id
    )
    logger.info(f"Handled /ask userId={user_id} username={username} questionLength={len(question)}")

# /discover (replaces /roadmap)
async def handle_discover(interaction: discord.Interaction, user_id: str, username: str):
    major = getattr(interaction.namespace, "major", "not specified")
    interests = getattr(interaction.namespace, "interests", "not specified")
    goals = getattr(interaction.namespace, "goals", "not specified")
    
    search_kw = " ".join(expand_search_terms(f"{major} {interests}"))
    question = (
        f"Generate a personalized club and event recommendation for a Rutgers student. "
        f"Major: {major}. Interests: {interests}. Goals: {goals}. "
        f"List all relevant clubs from context that match their profile (aim for up to 10 if available)."
    )

    content = await run_advisor(user_id, username, question, extra_clubs_search=search_kw)
    await send_with_guide(
        interaction,
        content,
        command="discover",
        user_text=f"{major} {interests} {goals}",
        user_id=user_id,
        topic="campus_clubs",
    )
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

    content = await run_advisor(user_id, username, question, extra_clubs_search=query)
    await send_with_guide(
        interaction, content, command="search", user_text=query, user_id=user_id, topic="campus_clubs"
    )
    logger.info(f"Handled /search userId={user_id} username={username} query={query}")

# /events (replaces /snipe)
async def handle_events(interaction: discord.Interaction, user_id: str, username: str):
    target = getattr(interaction.namespace, "target", None)
    if not target:
        await interaction.followup.send("Please provide a campus or club name.", ephemeral=True)
        return

    question = (
        f"Check upcoming events for \"{target}\". "
        f"List all upcoming events with their dates, times, and locations. "
        f"If no events are listed for \"{target}\" specifically, say so clearly and "
        f"provide the club's getINVOLVED page link from the CLUBS context so the user can check directly."
    )

    content = await run_advisor(user_id, username, question, extra_clubs_search=target)
    await send_with_guide(
        interaction, content, command="events", user_text=target, user_id=user_id, topic="campus_events"
    )
    logger.info(f"Handled /events userId={user_id} username={username} target={target}")

# /instagram
async def handle_instagram(interaction: discord.Interaction, user_id: str, username: str):
    club_name = getattr(interaction.namespace, "club", None)
    if not club_name:
        await interaction.followup.send("Please choose a club name.", ephemeral=True)
        return

    club = await find_club_by_name(club_name)
    if not club:
        await send_chunks(
            interaction,
            f'Could not find **{club_name}** in getINVOLVED data. '
            "Try `/search` with a slightly different name or check spelling.",
        )
        return

    await send_with_guide(
        interaction,
        format_instagram_message(club),
        command="instagram",
        user_text=club_name,
        user_id=user_id,
        topic="campus_clubs",
    )
    logger.info(f"Handled /instagram userId={user_id} club={club.get('name')}")

# /compare_prices — cheapest tri-state tickets across marketplaces
async def handle_compare_prices(interaction: discord.Interaction, user_id: str, username: str):
    search = getattr(interaction.namespace, "search", None)
    if not search or not search.strip():
        await interaction.followup.send("Enter a team, artist, or event to compare prices.", ephemeral=True)
        return
    category = _slash_choice_value(getattr(interaction.namespace, "category", None)) or "all"
    budget = getattr(interaction.namespace, "budget", None)
    content = await compare_ticket_prices(search=search.strip(), category=category, budget=budget)
    await send_with_guide(
        interaction, content, command="compare_prices", user_text=search, user_id=user_id, topic="tri_state"
    )
    logger.info(f"Handled /compare_prices userId={user_id} search={search[:60]}")

# /tickets — cheap tri-state tickets (sports, concerts, comedy, etc.)
async def handle_tickets(interaction: discord.Interaction, user_id: str, username: str):
    category = _slash_choice_value(getattr(interaction.namespace, "category", None)) or "all"
    search = getattr(interaction.namespace, "search", None)
    budget = getattr(interaction.namespace, "budget", None)

    content = await find_cheap_tickets(category=category, search=search, budget=budget)
    await send_with_guide(
        interaction,
        content,
        command="tickets",
        user_text=search or category,
        user_id=user_id,
        topic="tri_state",
    )
    logger.info(f"Handled /tickets userId={user_id} category={category} search={search}")

# /explore_events — discover events from interests with buy links
async def handle_explore_events(interaction: discord.Interaction, user_id: str, username: str):
    interests = getattr(interaction.namespace, "interests", None)
    if not interests:
        await interaction.followup.send("Tell me your interests (genres, teams, artists, vibes).", ephemeral=True)
        return

    category = _slash_choice_value(getattr(interaction.namespace, "category", None))
    budget = getattr(interaction.namespace, "budget", None)

    rutgers_ctx = ""
    tri_ctx = ""
    try:
        campus_events, tri_events = await asyncio.gather(
            search_events(interests),
            live_events_cache.search_tri_state_live(category=category or "all", max_results=8),
        )
        if campus_events:
            rutgers_ctx = format_events_context(campus_events)
        if tri_events:
            lines = ["Live tri-state listings (Ticketmaster):"]
            for e in tri_events[:6]:
                lines.append(
                    f"- {e.get('title')} on {e.get('date')} @ {e.get('campus')} "
                    f"[tickets]({e.get('rsvp_link')})"
                )
            tri_ctx = "\n".join(lines)
    except Exception as e:
        logger.warning(f"Events context skipped: {e}")

    combined_ctx = "\n\n".join(filter(None, [rutgers_ctx, tri_ctx]))
    content = await explore_events_by_interests(
        interests=interests,
        category=category,
        budget=budget,
        rutgers_events_context=combined_ctx,
    )
    await send_with_guide(
        interaction, content, command="explore_events", user_text=interests, user_id=user_id, topic="tri_state"
    )
    logger.info(f"Handled /explore_events userId={user_id} interests={interests[:80]}")

# /ask_tickets — conversational tri-state Q&A (builds interests over time)
async def handle_ask_tickets(interaction: discord.Interaction, user_id: str, username: str):
    question = getattr(interaction.namespace, "question", None)
    if not question:
        await interaction.followup.send("Ask a question about shows, tickets, or scenes you want to explore.", ephemeral=True)
        return

    history = await get_short_term_history(user_id)
    content = await ask_tri_state_question(question, history)
    await send_with_guide(
        interaction, content, command="ask_tickets", user_text=question, user_id=user_id, topic="tri_state"
    )
    asyncio.create_task(save_memory_async(user_id, username, question, content, None))
    logger.info(f"Handled /ask_tickets userId={user_id} len={len(question)}")

# /date_ideas — discover date ideas
async def handle_date_ideas(interaction: discord.Interaction, user_id: str, username: str):
    vibe = _slash_choice_value(getattr(interaction.namespace, "vibe", None)) or "any"
    interests = getattr(interaction.namespace, "interests", None)
    budget = getattr(interaction.namespace, "budget", None)

    content = await discover_first_date_ideas(vibe=vibe, interests=interests, budget=budget)
    await send_with_guide(
        interaction,
        content,
        command="date_ideas",
        user_text=interests or vibe,
        user_id=user_id,
        topic="date_ideas",
    )
    prompt = f"date_ideas vibe={vibe} interests={interests or ''}"
    asyncio.create_task(save_memory_async(user_id, username, prompt, content, None))
    logger.info(f"Handled /date_ideas userId={user_id} vibe={vibe}")

# /ask_date — Q&A about date ideas
async def handle_ask_date(interaction: discord.Interaction, user_id: str, username: str):
    question = getattr(interaction.namespace, "question", None)
    if not question:
        await interaction.followup.send("Ask anything about date ideas — plans, budget, vibe, logistics.", ephemeral=True)
        return

    history = await get_short_term_history(user_id)
    content = await ask_about_first_dates(question, history)
    await send_with_guide(
        interaction, content, command="ask_date", user_text=question, user_id=user_id, topic="date_ideas"
    )
    asyncio.create_task(save_memory_async(user_id, username, question, content, None))
    logger.info(f"Handled /ask_date userId={user_id} len={len(question)}")

# /whats_new — live upcoming campus + tri-state events (next 7 days)
async def handle_whats_new(interaction: discord.Interaction, user_id: str, username: str):
    await asyncio.gather(
        live_events_cache.refresh_campus(),
        live_events_cache.refresh_tri_state(),
    )
    campus_live = live_events_cache.campus_within_days(7)
    campus = await merge_campus_whats_new(campus_live, days=7)
    tri = live_events_cache.tri_state_within_days(7)
    if not tri:
        tri = live_events_cache.get_upcoming_tri_state()[:10]
    content = format_whats_new(campus, tri, days=7)
    await send_with_guide(
        interaction, content, command="whats_new", user_text="", user_id=user_id, topic="browse"
    )
    logger.info(
        f"Handled /whats_new userId={user_id} campus={len(campus)} tri_state={len(tri)}"
    )

# /start — route to commands or open a coach session
async def handle_start(interaction: discord.Interaction, user_id: str, username: str):
    topic = _slash_choice_value(getattr(interaction.namespace, "topic", None)) or "browse"
    details = (getattr(interaction.namespace, "details", None) or "").strip()
    start_session_flag = getattr(interaction.namespace, "start_session", False)
    if hasattr(start_session_flag, "value"):
        start_session_flag = bool(start_session_flag.value)

    if topic == "coach" or start_session_flag:
        goal = build_find_goal(topic, details)
        await handle_find(interaction, user_id, username, goal)
        logger.info("Handled /start → coach session userId=%s topic=%s", user_id, topic)
        return

    content = format_topic_guide(topic, details)
    await send_chunks(interaction, content)
    logger.info("Handled /start guide userId=%s topic=%s", user_id, topic)

# /find — start multi-turn coach session (thread)
async def handle_find_cmd(interaction: discord.Interaction, user_id: str, username: str):
    goal = getattr(interaction.namespace, "goal", None)
    if not goal or not goal.strip():
        await interaction.followup.send(
            "Tell me what you're trying to find — e.g. `one chill concert under $50` or `a CS club with hackathons`.",
            ephemeral=True,
        )
        return
    await handle_find(interaction, user_id, username, goal.strip())

# /continue — follow up in active coach session
async def handle_continue_cmd(interaction: discord.Interaction, user_id: str):
    message = getattr(interaction.namespace, "message", None)
    if not message or not message.strip():
        await interaction.followup.send("Add a follow-up message to continue your session.", ephemeral=True)
        return
    await handle_continue(interaction, user_id, message.strip())

# /session — coach session status
async def handle_session_cmd(interaction: discord.Interaction, user_id: str):
    await handle_session_status(interaction, user_id)

# /end_session
async def handle_end_session_cmd(interaction: discord.Interaction, user_id: str):
    await handle_end_session(interaction, user_id)

# /help
async def handle_help(interaction: discord.Interaction):
    help_text = (
        "**Rutgers S.E.E.R. Events Advisor — Commands**\n\n"
        "**Getting started**\n"
        "`/start [topic] [details]` — Tells you which commands to use, or **starts a coach session**.\n"
        "  _Pick a topic (clubs, tickets, dates…) or set **Start session: Yes**._\n\n"
        "`/ask <question>` — Ask anything about clubs, events, or campus life.\n"
        "`/discover <major> <interests> <goals>` — Get personalized club recommendations.\n"
        "`/search <query>` — Look up a specific club or event.\n"
        "`/events <target>` — Check upcoming events for a campus or club (live + database).\n"
        "`/whats_new` — Next 7 days: Rutgers events + live tri-state concerts/sports (Ticketmaster).\n"
        "`/instagram <club>` — Get a club's Instagram and getINVOLVED links.\n\n"
        "**Tri-state tickets & shows (NY / NJ / PA)**\n"
        "`/compare_prices <search> [category] [budget]` — Cheapest listings + links to SeatGeek, Gametime, StubHub, TM, etc.\n"
        "`/tickets <category> [search] [budget]` — Cheap tickets for sports, concerts, comedy, theater, festivals.\n"
        "`/explore_events <interests> [category] [budget]` — Discover events from your interests + buy links.\n"
        "`/ask_tickets <question>` — Ask anything; develop your interests in concerts, sports, comedy, etc.\n\n"
        "**Date Ideas**\n"
        "`/date_ideas <vibe> [interests] [budget]` — Curated date ideas with Maps/Yelp/OpenTable links.\n"
        "`/ask_date <question>` — Ask about plans, budget, vibe, or what to do.\n\n"
        "**Coach sessions (saved memory, 15 min idle timeout)**\n"
        "`/find <goal>` — Start a session; the agent asks follow-ups and narrows to **one pick**.\n"
        "  _Reply in the thread, or `/continue <message>`. Memory persists across bot restarts._\n"
        "`/continue <message>` — Keep going (resumes if the session went idle).\n"
        "`/session` — Status + time until auto-close.\n"
        "`/end_session` — Close the session.\n\n"
        "`/help` — Show this message.\n\n"
        "Campus events refresh automatically from getINVOLVED (live API + background sync).\n"
        "Tri-state: SeatGeek, Gametime, StubHub, etc. Dates: Google Maps, Yelp, OpenTable, Eventbrite."
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
    valid_commands = [
        'ask', 'discover', 'search', 'events', 'instagram',
        'tickets', 'compare_prices', 'explore_events', 'ask_tickets',
        'date_ideas', 'ask_date', 'whats_new', 'start',
        'find', 'continue', 'session', 'end_session', 'help',
    ]
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
        elif command_name == 'instagram':
            await handle_instagram(interaction, user_id, username)
        elif command_name == 'tickets':
            await handle_tickets(interaction, user_id, username)
        elif command_name == 'compare_prices':
            await handle_compare_prices(interaction, user_id, username)
        elif command_name == 'explore_events':
            await handle_explore_events(interaction, user_id, username)
        elif command_name == 'ask_tickets':
            await handle_ask_tickets(interaction, user_id, username)
        elif command_name == 'date_ideas':
            await handle_date_ideas(interaction, user_id, username)
        elif command_name == 'ask_date':
            await handle_ask_date(interaction, user_id, username)
        elif command_name == 'whats_new':
            await handle_whats_new(interaction, user_id, username)
        elif command_name == 'start':
            await handle_start(interaction, user_id, username)
        elif command_name == 'find':
            await handle_find_cmd(interaction, user_id, username)
        elif command_name == 'continue':
            await handle_continue_cmd(interaction, user_id)
        elif command_name == 'session':
            await handle_session_cmd(interaction, user_id)
        elif command_name == 'end_session':
            await handle_end_session_cmd(interaction, user_id)
        elif command_name == 'help':
            await handle_help(interaction)
    except Exception as e:
        logger.error(f"Interaction handler error: {e}")
        try:
            await interaction.edit_original_response(content="Sorry, something went wrong. Please try again later.")
        except Exception as edit_err:
            logger.error(f"Fallback edit failed: {edit_err}")
