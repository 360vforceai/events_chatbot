import sys
import time
from pathlib import Path

# Allow `python discord_bot/bot.py` from the bot/ directory (README workflow).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import discord
from discord.ext import commands
from discord import app_commands
from app.config import settings
import logging
from discord_bot.interaction_handler import handle_interaction, purge_interactions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

# ---------------------------------------------------------------------------
# Club name cache — refreshed every 5 minutes so autocomplete stays fast
# ---------------------------------------------------------------------------
_club_cache: list[str] = []
_club_cache_ts: float = 0
_CACHE_TTL = 300  # seconds

async def _get_club_names() -> list[str]:
    global _club_cache, _club_cache_ts
    if time.time() - _club_cache_ts < _CACHE_TTL and _club_cache:
        return _club_cache
    try:
        from app.db.client import get_supabase
        sb = get_supabase()
        rows = sb.table("clubs").select("name").execute().data
        _club_cache = sorted(r["name"].strip() for r in rows if r.get("name"))
        _club_cache_ts = time.time()
        logger.info(f"Club autocomplete cache refreshed ({len(_club_cache)} clubs)")
    except Exception as e:
        logger.error(f"Failed to refresh club cache: {e}")
    return _club_cache


async def club_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    names = await _get_club_names()
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
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        purge_interactions.start()
        # Pre-warm the club cache on startup
        await _get_club_names()
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

@client.tree.command(name="help", description="Show all available commands")
async def help_cmd(interaction: discord.Interaction):
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
