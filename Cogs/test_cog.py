# cog for testing embeds and views

import logging
import random

from discord import app_commands, Interaction
from discord.ext import commands

from Actions.join_draft_act import join_draft
from Database.Models.card import Card
from Database.Models.draft import Draft
from Database.Models.pack import Pack
from Database.Models.user import User
from Database.draft_setup import create_draft, get_cards_from_data
from Messages import finished_draft_global_msg, player_pick_msg, open_draft_msg
from Tests.test_constants import DRAFT_OPTIONS, CARDS_LIST_LONG


class TestCog(commands.GroupCog, name="test"):
    def __init__(self, bot):
        logging.info("Loading Cog: test_cog.py")
        self.bot = bot

    @app_commands.command()
    async def open_draft_message(self, interaction: Interaction):
        await interaction.response.defer()

        # clear test draft
        old_draft = await Draft.get_or_none(name=DRAFT_OPTIONS["name"])
        if old_draft:
            await old_draft.delete()

        # create test draft
        draft = await create_draft(**DRAFT_OPTIONS)

        # send test notification
        message = await open_draft_msg.get_message(
            draft_name=DRAFT_OPTIONS["name"], interaction=interaction
        )
        await interaction.followup.send(**message)

    @app_commands.command()
    async def finished_global_notification(self, interaction: Interaction):
        # clear test draft
        old_draft = await Draft.get_or_none(name=DRAFT_OPTIONS["name"])
        if old_draft:
            await old_draft.delete()

        # create test draft
        draft = await create_draft(**DRAFT_OPTIONS)

        # send test notification
        message = await finished_draft_global_msg.get_message(draft)
        await interaction.followup.send(**message)

    @app_commands.command()
    async def player_pick_card_msg(self, interaction: Interaction):
        await interaction.response.defer()

        # creating draft, loading cards and shuffling packs and distributing doesn't make sense here
        # just instantiate the pack with cards

        # clear test draft
        old_draft = await Draft.get_or_none(name=DRAFT_OPTIONS["name"])
        if old_draft:
            await old_draft.delete()

        # create test draft
        draft = await create_draft(**DRAFT_OPTIONS)

        cards = []
        for card in random.sample(CARDS_LIST_LONG, 8):
            cards.append(await Card.create(**card))

        pack = await Pack.create(draft=draft)
        await pack.cards.add(*cards)

        message = await player_pick_msg.get_message(pack)

        await interaction.followup.send(**message)

    # @app_commands.command()
    # async def run_draft(self, interaction: Interaction, draft_name: str, interval: int = 5):
    #     cog = self.bot.get_cog("DraftCog")
    #     cog.task_launcher(draft_name, seconds=interval)
    #
    #     await interaction.response.send_message(f"Running draft: {draft_name} (but not really)")

    @app_commands.command()
    async def reset_users(self, interaction: Interaction):
        # reset decks on users
        async for user in User.all():
            user.deck_string = ""
            await user.save()

        await interaction.response.send_message("Users reset")

    @app_commands.command()
    async def setup_ready_draft(self, interaction: Interaction):
        await interaction.response.defer()

        # reset decks on users
        async for user in User.all():
            user.deck_string = ""
            await user.save()

        # clear test draft
        old_draft = await Draft.get_or_none(name=DRAFT_OPTIONS["name"])
        if old_draft:
            await old_draft.delete()

        # create test draft
        draft = await create_draft(**DRAFT_OPTIONS)

        await get_cards_from_data(CARDS_LIST_LONG, draft)

        user = await join_draft(draft.name, interaction.user.id)

        await interaction.followup.send(f"{draft.name} is ready to be run.")

    # @app_commands.command()
    # async def create_draft(self, interaction: Interaction):
    #     await create_draft(**DRAFT_OPTIONS)
    #
    #     await interaction.response.send_message("Test draft created!")


async def setup(bot):  # an extension must have a setup function
    await bot.add_cog(TestCog(bot))  # adding a cog
