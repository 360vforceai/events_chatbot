import discord
from discord.ext import commands
from app.config import settings

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "discord_bot.cogs.discover",
    "discord_bot.cogs.events",
    "discord_bot.cogs.subscribe",
]


@bot.event
async def on_ready():
    print(f"SEER Bot online as {bot.user}")
    for cog in COGS:
        await bot.load_extension(cog)
    await bot.tree.sync(guild=discord.Object(id=int(settings.discord_guild_id)))


if __name__ == "__main__":
    bot.run(settings.discord_bot_token)
