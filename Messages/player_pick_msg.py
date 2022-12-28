import asyncio
from collections import deque
from typing import List

import discord
from discord import ui, Interaction, Embed

import constants
from Database.Models.pack import Pack


class View(ui.View):
    def __init__(self, pack: Pack, embeds: List[Embed]):
        self._embeds = embeds
        self._queue = deque(embeds)
        self._initial = embeds[0]
        self._current_card_index = 0
        self._len = len(embeds)
        self.response = None
        self.pack = pack
        self._pick_event = asyncio.Event()

        super().__init__(timeout=60 * 3)

    @property
    def initial(self) -> Embed:
        return self._initial

    @property
    def current_card_index(self) -> int:
        return self._current_card_index

    @property
    def pick_event(self) -> asyncio.Event:
        return self._pick_event

    async def auto_pick(self):
        for child in self.children:
            child.disabled = True

        new_embed = self._queue[0]
        new_embed.set_footer(
            text="This card has been picked automatically because you took too long to pick!"
        )

        await self.response.edit(view=self, embed=new_embed)

    @ui.button(emoji="\N{LEFTWARDS BLACK ARROW}")
    async def previous_embed(self, interaction: Interaction, _):
        self._queue.rotate(1)
        self._current_card_index = (self._current_card_index - 1) % self._len
        await interaction.response.edit_message(embed=self._queue[0])

    @ui.button(label="Pick this card \N{DIRECT HIT}", style=discord.ButtonStyle.primary)
    async def pick_card(self, interaction: Interaction, _):
        try:
            self._pick_event.set()
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        # update the embed
        # "you picked this" message, disable all buttons

        self._pick_event.set()

        # disable all buttons
        for child in self.children:
            child.disabled = True

        new_embed = self._queue[0]
        new_embed.set_footer(text="You picked this card!")
        await interaction.response.edit_message(embed=new_embed, view=self)

        self.stop()

    @ui.button(emoji="\N{BLACK RIGHTWARDS ARROW}")
    async def next_embed(self, interaction: Interaction, _):
        self._queue.rotate(-1)
        self._current_card_index = (self._current_card_index + 1) % self._len
        await interaction.response.edit_message(embed=self._queue[0])


async def get_message(pack: Pack, pack_index: str = "1/1"):
    await pack.fetch_related("cards")
    cards = await pack.cards

    embeds = []
    for index, card in enumerate(cards):
        embed = Embed(
            title=card.name,
            url=card.link,
            description=f"Pack {pack_index} - Card {index + 1}/{len(cards)}",
            color=constants.EMBED_COLOR,
        )
        embed.set_image(url=card.link)
        embeds.append(embed)

    view = View(pack, embeds)

    return {
        "embed": view.initial,
        "view": view,
    }
