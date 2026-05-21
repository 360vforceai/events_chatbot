import discord
from discord import app_commands
from discord.ext import commands
import httpx

API_BASE = "http://localhost:8000"


class SubscribeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="subscribe", description="Subscribe to alerts for a club or category"
    )
    @app_commands.describe(
        target="Club name or category slug (e.g. 'RUMAD' or 'category:hackathon')"
    )
    async def subscribe(self, interaction: discord.Interaction, target: str):
        await interaction.response.defer(ephemeral=True)
        payload = {
            "discord_user_id": str(interaction.user.id),
            "action": "subscribe",
            "target": target,
        }
        async with httpx.AsyncClient() as client:
            await client.post(f"{API_BASE}/users/subscribe", json=payload)
        await interaction.followup.send(
            f"✅ Subscribed to **{target}**. You'll get DMs when new events are posted.",
            ephemeral=True,
        )

    @app_commands.command(name="unsubscribe", description="Remove a subscription")
    @app_commands.describe(target="Club name or category slug to unsubscribe from")
    async def unsubscribe(self, interaction: discord.Interaction, target: str):
        await interaction.response.defer(ephemeral=True)
        payload = {
            "discord_user_id": str(interaction.user.id),
            "action": "unsubscribe",
            "target": target,
        }
        async with httpx.AsyncClient() as client:
            await client.post(f"{API_BASE}/users/subscribe", json=payload)
        await interaction.followup.send(f"Unsubscribed from **{target}**.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(SubscribeCog(bot))
