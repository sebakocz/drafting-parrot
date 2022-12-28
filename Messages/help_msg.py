import discord
from discord import ui, Interaction

from Actions import create_draft_act
from Messages import show_all_drafts_msg, explain_msg
from constants import EMBED_COLOR


class View(ui.View):
    def __init__(self):
        super().__init__()
        url = "https://github.com/sebakocz/mopping-mucus"

        # Link buttons cannot be made with the decorator
        # Therefore we have to manually create one.
        # We add the quoted url to the button, and add the button to the view.
        self.add_item(ui.Button(label="Contribute \N{PERSONAL COMPUTER}", url=url))

    # button for showing all drafts
    @ui.button(label="Show Drafts \N{EYES}", style=discord.ButtonStyle.primary)
    async def show_all_drafts(self, interaction: Interaction, _):
        message = await show_all_drafts_msg.get_message()
        await interaction.response.send_message(**message)

    # button to create a draft
    @ui.button(label="Create Draft \N{RAISED HAND}", style=discord.ButtonStyle.primary)
    async def join_draft(self, interaction: Interaction, _):
        await create_draft_act.create_draft_dis(interaction)

    # button to explain what a draft is
    @ui.button(label="Cube drafts? \N{ICE CUBE}", style=discord.ButtonStyle.primary)
    async def explain(self, interaction: Interaction, _):
        message = explain_msg.get_message()
        await interaction.response.send_message(**message)


async def get_message():

    # intro message
    embed = discord.Embed(
        title="Welcome to Mopping Mucus!",
        description="Mopping Mucus is a Discord bot for cube drafts. It is currently in development, so please be patient with bugs and missing features. Here are some of the things you can do:",
        color=EMBED_COLOR,
    )

    # info about cmds
    embed.add_field(
        name="/show_all_drafts",
        value="You can see all ongoing drafts by typing `/show_all_drafts` or by simply clicking the button below.",
        inline=False,
    )

    embed.add_field(
        name="/join_draft",
        value="When you find a cool draft you're interesting in join by typing `/join_draft <draft_name>`",
        inline=False,
    )

    embed.add_field(
        name="/create_draft",
        value="If you can't find a draft how about creating one yourself? You can create a draft by typing `/create_draft` or simply click the button below.",
        inline=False,
    )

    return {
        "embed": embed,
        "view": View(),
    }
