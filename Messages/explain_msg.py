import discord

from constants import EMBED_COLOR


def get_message():

    embed = discord.Embed(
        color=EMBED_COLOR,
        title="What is a cube draft?",
        description="""
A cube draft is a way to play Collective with a group of friends. You can think of it as a tournament, but you didn't bring your deck yet.

In a Collective draft, players are seated around a table and given a set of packs containing randomized cards from a particular Collective cube. Each player opens a pack, selects one card from it, and then passes the remaining cards to the player on their left. This process is repeated until all the cards in the pack have been selected. The players then open their second pack and repeat the process, this time passing the packs to the right. This continues until all the packs have been opened and all the cards have been selected.

After the draft, players use the cards they have selected to construct a deck, which they will use to play against other players in the draft. The goal is to build a strong, cohesive deck that can effectively utilize the cards you have drafted.
""",
    )

    return {"embed": embed}
