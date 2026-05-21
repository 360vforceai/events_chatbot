import discord
from discord import app_commands
from discord.ext import commands
import httpx

API_BASE = "http://localhost:8000"


class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="events", description="Browse upcoming campus events")
    @app_commands.describe(
        campus="Filter by campus (Busch, College Ave, Livi, Cook)",
        event_type="Filter by type (social, workshop, competition...)",
        free_food="Only show events with free food",
    )
    async def events(
        self,
        interaction: discord.Interaction,
        campus: str = None,
        event_type: str = None,
        free_food: bool = False,
    ):
        await interaction.response.defer(thinking=True)
        payload = {
            "campus": campus,
            "event_type": event_type,
            "free_food": free_food or None,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{API_BASE}/events/search", json=payload)
            events = resp.json()
        if not events:
            await interaction.followup.send("No events found matching your filters.")
            return
        embed = discord.Embed(title="Upcoming Events", color=0x3B5BDB)
        for ev in events[:8]:
            val = f"{ev['date']} @ {ev['time']}  |  {ev['location']}"
            if ev.get("free_food"):
                val += "  🍕 Free food"
            embed.add_field(name=ev["title"], value=val, inline=False)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(EventsCog(bot))
