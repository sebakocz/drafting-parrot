from discord import Embed

from Components.constants import EMBED_COLOR
from Components.notification_utils import settings_field, players_field
from Database.Models.draft import Draft


async def get_notification(draft: Draft):
    await draft.fetch_related("participants", "settings")

    embed = Embed(
        title=f"{draft.name}",
        description=f"{draft.description}",
        color=EMBED_COLOR,
    )

    # settings info
    embed.add_field(**settings_field(draft.settings))

    # players list
    embed.add_field(**players_field(draft))

    # deckbuilding reminder
    embed.add_field(
        name="Time to brew!",
        value="You should be able to find your cardlist in your DMs. When you're done brewing, use the `/submit_deck` command here to submit your decklist.",
        inline=False,
    )

    return embed