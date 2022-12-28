import discord
from discord import ui, Interaction

import Actions.join_draft_act
from Messages.message_utils import settings_field, players_field
from Database.Models.draft import Draft
from constants import EMBED_COLOR


class Embed(discord.Embed):
    def __init__(self, interaction: Interaction, draft, **kwargs):
        super().__init__(
            title=f"{draft.name}",
            description=f"{draft.description}",
            color=EMBED_COLOR,
            **kwargs,
        )

        self.interaction = interaction
        self.draft = draft

        # draft creator
        # smelly-m2m
        creator = interaction.guild.get_member(draft.owner[0].discord_id)
        self.set_author(
            name=f"Draft created by {creator.nick or creator.name}",
            icon_url=creator.display_avatar,
        )

        # settings info
        self.add_field(**settings_field(draft.settings))

        # players list
        self.add_field(**players_field(draft))


class View(ui.View):
    def __init__(self, draft: Draft):
        super().__init__()
        url = "https://collectivedeck.codes/brew"

        self.draft = draft

        # Link buttons cannot be made with the decorator
        # Therefore we have to manually create one.
        # We add the quoted url to the button, and add the button to the view.
        self.add_item(ui.Button(label="View Cardpool \N{EYES}", url=url))

    # button to join the draft
    @ui.button(label="Join Draft \N{RAISED HAND}", style=discord.ButtonStyle.primary)
    async def join_draft(self, interaction: Interaction, _):
        try:
            response = await Actions.join_draft_act.join_draft(
                self.draft.name, interaction.user.id
            )
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        # update the embed
        await self.draft.fetch_related("participants")
        new_embed = Embed(interaction, self.draft)
        await interaction.response.edit_message(embed=new_embed, view=self)

        # await interaction.response.send_message(f"{interaction.user.mention} joined the draft!")


async def get_message(draft_name, interaction):
    draft = await Draft.get(name=draft_name).prefetch_related(
        "owner", "participants", "settings"
    )

    return {
        "embed": Embed(interaction, draft),
        "view": View(draft),
    }
