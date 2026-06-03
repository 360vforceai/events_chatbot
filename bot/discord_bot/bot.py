import sys
from pathlib import Path

# Allow `python discord_bot/bot.py` from the bot/ directory (README workflow).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import discord
from discord.ext import commands
from discord import app_commands
from app.config import settings
import logging
from discord_bot.interaction_handler import handle_interaction, purge_interactions
from discord_bot.coach_handler import handle_coach_thread_message
from discord_bot import club_cache, sync_tasks
from app.services.ticket_service import EVENT_CATEGORIES
from app.services.date_ideas_service import DATE_VIBES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

TICKET_CATEGORY_CHOICES = [
    app_commands.Choice(name=label, value=key)
    for key, label in EVENT_CATEGORIES.items()
]

DATE_VIBE_CHOICES = [
    app_commands.Choice(name=label, value=key)
    for key, label in DATE_VIBES.items()
]


async def club_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    names = await club_cache.get_club_names()
    current_lower = current.lower()
    matches = [n for n in names if current_lower in n.lower()]
    # Put names that START with the typed text first
    matches.sort(key=lambda n: (not n.lower().startswith(current_lower), n))
    return [
        app_commands.Choice(name=n[:100], value=n[:100])
        for n in matches[:25]
    ]


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------

class SeerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        purge_interactions.start()
        sync_tasks.start_background_tasks(self)
        await club_cache.get_club_names()
        guild_id = int(settings.discord_guild_id)
        guild = discord.Object(id=guild_id)
        self.tree.copy_global_to(guild=guild)
        try:
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %s slash command(s) to guild %s", len(synced), guild_id)
        except discord.Forbidden:
            logger.error(
                "Slash command sync failed (403 Missing Access) for guild %s. "
                "Invite the bot to that server with scopes bot + applications.commands, "
                "then confirm DISCORD_GUILD_ID is the Server ID (not a channel ID).",
                guild_id,
            )

client = SeerBot()

@client.event
async def on_ready():
    logger.info(f"Discord bot ready. Logged in as {client.user.name}")
    await sync_tasks.run_initial_sync()


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    try:
        await handle_coach_thread_message(message)
    except Exception as e:
        logger.error("Coach thread message error: %s", e)

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@client.tree.command(name="ask", description="Ask the Rutgers Events advisor any question")
@app_commands.describe(question="Your question about clubs, events, etc.")
async def ask_cmd(interaction: discord.Interaction, question: str):
    await handle_interaction(interaction)

@client.tree.command(name="discover", description="Generate a personalized club recommendation")
@app_commands.describe(major="Your major", interests="Your interests", goals="Your goals")
async def discover_cmd(interaction: discord.Interaction, major: str, interests: str, goals: str):
    await handle_interaction(interaction)

@client.tree.command(name="search", description="Look up a specific club or event")
@app_commands.describe(query="Club or event name")
@app_commands.autocomplete(query=club_autocomplete)
async def search_cmd(interaction: discord.Interaction, query: str):
    await handle_interaction(interaction)

@client.tree.command(name="events", description="Check upcoming events")
@app_commands.describe(target="Campus or club name")
@app_commands.autocomplete(target=club_autocomplete)
async def events_cmd(interaction: discord.Interaction, target: str):
    await handle_interaction(interaction)

@client.tree.command(name="instagram", description="Get a club's Instagram and links")
@app_commands.describe(club="Club name")
@app_commands.autocomplete(club=club_autocomplete)
async def instagram_cmd(interaction: discord.Interaction, club: str):
    await handle_interaction(interaction)

@client.tree.command(
    name="tickets",
    description="Find cheap tri-state tickets (sports, concerts, comedy, theater)",
)
@app_commands.describe(
    category="Type of event",
    search="Team, artist, or keyword (optional)",
    budget="Budget hint, e.g. under $40 (optional)",
)
@app_commands.choices(category=TICKET_CATEGORY_CHOICES)
async def tickets_cmd(
    interaction: discord.Interaction,
    category: app_commands.Choice[str],
    search: str | None = None,
    budget: str | None = None,
):
    await handle_interaction(interaction)

@client.tree.command(
    name="explore_events",
    description="Discover tri-state events from your interests with ticket links",
)
@app_commands.describe(
    interests="What you're into — artists, teams, genres, vibes",
    category="Optional filter: sports, concert, comedy, etc.",
    budget="Optional budget cap, e.g. under $50",
)
@app_commands.choices(category=TICKET_CATEGORY_CHOICES)
async def explore_events_cmd(
    interaction: discord.Interaction,
    interests: str,
    category: app_commands.Choice[str] | None = None,
    budget: str | None = None,
):
    await handle_interaction(interaction)

@client.tree.command(
    name="ask_tickets",
    description="Ask about tri-state shows and tickets — explore and develop your interests",
)
@app_commands.describe(
    question="e.g. I want to get into jazz concerts cheaply — where do I start?",
)
async def ask_tickets_cmd(interaction: discord.Interaction, question: str):
    await handle_interaction(interaction)

@client.tree.command(
    name="date_ideas",
    description="Discover date ideas near Rutgers with planning links",
)
@app_commands.describe(
    vibe="Date vibe",
    interests="Optional — coffee, museums, live music, etc.",
    budget="Optional — e.g. under $30 each",
)
@app_commands.choices(vibe=DATE_VIBE_CHOICES)
async def date_ideas_cmd(
    interaction: discord.Interaction,
    vibe: app_commands.Choice[str],
    interests: str | None = None,
    budget: str | None = None,
):
    await handle_interaction(interaction)

@client.tree.command(
    name="ask_date",
    description="Ask anything about date ideas near Rutgers",
)
@app_commands.describe(
    question="e.g. What's a low-pressure date idea if we both love food?",
)
async def ask_date_cmd(interaction: discord.Interaction, question: str):
    await handle_interaction(interaction)

@client.tree.command(
    name="whats_new",
    description="Next 7 days: Rutgers events + live tri-state concerts & sports",
)
async def whats_new_cmd(interaction: discord.Interaction):
    await handle_interaction(interaction)

@client.tree.command(name="help", description="Show all available commands")
async def help_cmd(interaction: discord.Interaction):
    await handle_interaction(interaction)


@client.tree.command(
    name="find",
    description="Start a coach session — the agent helps you narrow down to one event or plan",
)
@app_commands.describe(
    goal="What you're trying to find — e.g. one cheap concert this month, a CS club to join",
)
async def find_cmd(interaction: discord.Interaction, goal: str):
    await handle_interaction(interaction)


@client.tree.command(
    name="continue",
    description="Continue your active coach session with a follow-up message",
)
@app_commands.describe(message="Elaborate, answer a question, or say 'just pick one for me'")
async def continue_cmd(interaction: discord.Interaction, message: str):
    await handle_interaction(interaction)


@client.tree.command(name="session", description="Show your active coach session status")
async def session_cmd(interaction: discord.Interaction):
    await handle_interaction(interaction)


@client.tree.command(name="end_session", description="End your active coach session")
async def end_session_cmd(interaction: discord.Interaction):
    await handle_interaction(interaction)


@client.tree.command(
    name="compare_prices",
    description="Find cheapest tri-state tickets (comedy to NBA) across all major sellers",
)
@app_commands.describe(
    search="Team, artist, or event — e.g. NBA Finals, comedy Newark, Taylor Swift",
    category="Optional: sports, concert, comedy, theater",
    budget="Optional — e.g. under 75",
)
@app_commands.choices(category=TICKET_CATEGORY_CHOICES)
async def compare_prices_cmd(
    interaction: discord.Interaction,
    search: str,
    category: app_commands.Choice[str] | None = None,
    budget: str | None = None,
):
    await handle_interaction(interaction)

if __name__ == "__main__":
    token = settings.discord_bot_token
    if not token:
        logger.error("DISCORD_BOT_TOKEN is not set")
        exit(1)
    try:
        client.run(token)
    except discord.LoginFailure:
        logger.error(
            "Discord login failed. Reset the bot token in the Developer Portal "
            "and update DISCORD_BOT_TOKEN in bot/.env (no spaces after =)."
        )
        raise
