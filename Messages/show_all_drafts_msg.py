import discord

from Database.Models.draft import Draft
from constants import EMBED_COLOR


async def get_message():
    drafts = await Draft.all()
    embed = discord.Embed(title="All drafts", color=EMBED_COLOR)
    for draft in drafts:
        embed.add_field(
            name=draft.name,
            value=f"Status: {draft.status}",
            inline=False,
        )

    return {"embed": embed}
