import discord
from discord.ext import commands
from discord import app_commands
from app.config import settings
import logging
from discord_bot.interaction_handler import handle_interaction, purge_interactions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

class SeerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        purge_interactions.start()
        guild = discord.Object(id=int(settings.discord_guild_id))
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

client = SeerBot()

@client.event
async def on_ready():
    logger.info(f"Discord bot ready. Logged in as {client.user.name}")

# Define commands globally so they sync to the guild
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
async def search_cmd(interaction: discord.Interaction, query: str):
    await handle_interaction(interaction)

@client.tree.command(name="events", description="Check upcoming events")
@app_commands.describe(target="Campus or club name")
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
    client.run(token)
