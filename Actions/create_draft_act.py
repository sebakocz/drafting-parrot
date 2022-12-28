import logging

import discord
import requests
from discord import Interaction

from constants import cardpool_format_example
from Database.Models.draft import PickType
from Database.draft_setup import create_draft, get_cards_from_data
from Messages import open_draft_msg
from Utils.collective_api import get_card_data, ApiError

# I don't like this in Actions, discord interactions should be elsewhere, I wanted actions to be pure without chat stuff


async def create_draft_dis(interaction: Interaction):
    await interaction.response.defer()

    async def get_answer(question, timeout=60):
        await interaction.user.dm_channel.send(question)
        return await interaction.client.wait_for(
            "message",
            check=lambda m: m.author == interaction.user
            and m.channel == interaction.user.dm_channel,
            timeout=timeout,
        )

    try:
        await interaction.user.create_dm()
    except:
        await interaction.followup.send(
            "I can't dm you, please enable dms from server members."
        )
        return

    await interaction.followup.send("I've sent you a dm with instructions.")

    try:
        await interaction.user.dm_channel.send("Hello! Let's create a draft!")

        # get draft name
        draft_name_msg = await get_answer("What is the name of the draft?")
        draft_name = draft_name_msg.content.strip()

        # get draft description
        draft_description_msg = await get_answer(
            "What is the description of the draft? Mention special rules here as well."
        )
        draft_description = draft_description_msg.content.strip()

        # get pick type
        draft_pick_type_msg = await get_answer(
            "What is the pick type? `blueprint` -> Up to 3 slots, `singleton` -> 1 slot",
        )
        draft_pick_type = draft_pick_type_msg.content.strip()
        if draft_pick_type not in [pick_type.value for pick_type in PickType]:
            await interaction.user.dm_channel.send(
                "Invalid pick type. Please try again."
            )
            return

        # pack options
        # get packs per player
        draft_packs_per_player_msg = await get_answer("How many packs per player?")
        draft_packs_per_player = int(draft_packs_per_player_msg.content.strip())

        # get cards per pack
        draft_cards_per_pack_msg = await get_answer("How many cards per pack?")
        draft_cards_per_pack = int(draft_cards_per_pack_msg.content.strip())

        # get thinking time
        draft_seconds_per_pick_msg = await get_answer(
            "How much thinking time per pick? (in seconds)"
        )
        seconds_per_pick = int(draft_seconds_per_pick_msg.content.strip())

        # get max participants
        draft_max_participants_msg = await get_answer("How many maximum participants?")
        draft_max_participants = int(draft_max_participants_msg.content.strip())

        # get draft file
        draft_cardpool_msg = await get_answer(
            "Please send me a .txt file with the cardpool for the draft. The format is as follows:\n"
            + cardpool_format_example,
        )
        draft_cardpool_url = draft_cardpool_msg.attachments[0].url
        draft_cardpool_request = requests.get(draft_cardpool_url)
        draft_cardpool_lines = draft_cardpool_request.text.splitlines()

        # message to confirm processing
        duration = round(len(draft_cardpool_lines) / 100)
        await interaction.user.dm_channel.send(
            f"Thank you! I'll create the draft now. Please wait, this may take {'less than a minute' if duration <= 1 else f'{duration} minutes'}."
        )

    except TimeoutError:
        await interaction.user.dm_channel.send(
            "You took too long to respond, please try again."
        )
        return
    except:
        logging.exception("Error while creating draft (1/2)")
        await interaction.user.dm_channel.send(
            "Something went wrong during the draft creation process (1/2), please try again."
        )
        return

    try:
        # fetch cards
        draft_cards_data = await get_card_data(draft_cardpool_lines)
    except ApiError as e:
        await interaction.user.dm_channel.send(
            f"Something went wrong while fetching the card data. Please make sure the cardpool is correct and try again.\n{e}"
        )
        return

    try:
        # create draft in database
        draft = await create_draft(
            owner_discord_id=interaction.user.id,
            name=draft_name,
            description=draft_description,
            pick_type=PickType(draft_pick_type),
            packs_per_player=draft_packs_per_player,
            cards_per_pack=draft_cards_per_pack,
            seconds_per_pick=seconds_per_pick,
            max_participants=draft_max_participants,
        )

        # fill draft with cardpool
        await get_cards_from_data(draft_cards_data, draft)

        # create draft messages for dm and channel
        message = await open_draft_msg.get_message(
            draft_name=draft_name, interaction=interaction
        )

        await interaction.user.dm_channel.send(
            "Draft created successfully! Other players can join the draft now."
        )
        await interaction.followup.send(**message)

    except:
        logging.exception("Error while creating draft (2/2)")
        await interaction.user.dm_channel.send(
            "Something went wrong during the draft creation process (2/2), please try again."
        )
        return
