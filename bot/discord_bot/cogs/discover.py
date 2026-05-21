import discord
from discord import app_commands
from discord.ext import commands
import httpx

API_BASE = "http://localhost:8000"


class DiscoverModal(discord.ui.Modal, title="Discover Clubs"):
    major = discord.ui.TextInput(label="Your major", placeholder="e.g. Computer Science")
    interests = discord.ui.TextInput(
        label="Interests (comma-sep)", placeholder="e.g. AI, hackathons, music"
    )
    goals = discord.ui.TextInput(
        label="Career / personal goals", placeholder="e.g. software engineering internship"
    )
    campus = discord.ui.TextInput(
        label="Preferred campus", placeholder="Busch / College Ave / Livi / Cook"
    )
    commitment = discord.ui.TextInput(
        label="Time commitment", placeholder="casual / moderate / high"
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        profile = {
            "major": self.major.value,
            "interests": [i.strip() for i in self.interests.value.split(",")],
            "goals": self.goals.value,
            "campus": self.campus.value,
            "time_commitment": self.commitment.value,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{API_BASE}/recommend", json=profile)
            results = resp.json()
        embed = discord.Embed(title="Your Club Recommendations", color=0xCC0033)
        for r in results[:5]:
            embed.add_field(name=r["name"], value=r["reason"], inline=False)
        await interaction.followup.send(embed=embed)


class DiscoverCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="discover", description="Find clubs tailored to your interests"
    )
    async def discover(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DiscoverModal())


async def setup(bot):
    await bot.add_cog(DiscoverCog(bot))
