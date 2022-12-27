# cog for starting and running a draft
import asyncio
import logging
from datetime import datetime

import discord
import requests
from discord import app_commands, Interaction, Attachment
from discord.ext import commands, tasks

from Components import (
    user_actions,
    player_pick_notification,
    finished_draft_global_notification,
    open_draft_notification,
)
from Components.constants import EMBED_COLOR
from Database.Models.draft import Draft, DraftStatus, PickType
from Database.Models.pack import Pack
from Database.Models.user import User
from Database.draft_setup import create_draft, get_cards_from_data
from Utils.collective_api import get_card_data, ApiError

cardpool_format_example = """```
https://files.collective.gg/p/cards/9803f3b0-2b61-11eb-a0f9-41a57384b22e-s.png
https://files.collective.gg/p/cards/ee442390-8fce-11eb-9348-5bd7bae36142-s.png
https://files.collective.gg/p/cards/17d9dd00-627d-11eb-96e6-21b90bd58800-s.png
Read Leaf Warshaman
Huntsman's Return
Head Chieftain Dzikus
00cb6290-61b4-11ed-82b4-833eed596c50
612f6fe0-f3e2-11ec-a26e-9defb71be79c
d43cdd40-612b-11ed-82b4-833eed596c50
```"""


class DraftCog(commands.Cog):
    def __init__(self, bot):
        logging.info("Loading Cog: draft_cog.py")
        self.bot = bot

    async def draft_step(self, draft_name: str):
        """Handles the draft loop."""

        # Get the draft and its settings
        draft = await Draft.get(name=draft_name)
        await draft.fetch_related("settings", "participants", "packs")
        settings, participants = draft.settings, draft.participants

        # check if draft is still running
        if draft.status != DraftStatus.RUNNING.value:
            logging.info(f"Draft {draft.name} is not running, stopping draft loop.")
            return

        # TODO: you should illustrate this process with a diagram

        # fetch a pack for each player
        logging.info(
            f"FETCH - Packs for {len(participants)} players in draft {draft_name}"
        )
        packs = await Pack.filter(draft=draft).limit(len(participants))
        # shift packs
        cycle_index = draft.rounds_completed % len(participants)
        packs = packs[cycle_index:] + packs[:cycle_index]
        # log packs
        for pack in packs:
            await pack.fetch_related("cards")
            logging.info(f"FETCH - Pack {pack.id} contains {len(pack.cards)} cards")

        # Send an interaction view panel and notification to each participant
        views = []
        for participant, pack in zip(participants, packs):
            # Send an interaction view panel to the participant with their current pack
            logging.info(
                f"SEND - Pack to user <{participant.discord_id}> in draft {draft_name} and awaiting response..."
            )
            view = await player_pick_notification.get_notification(
                pack,
                f"{int((draft.rounds_completed) / settings.cards_per_pack) +1}/{settings.packs_per_player}",
            )
            out = await self.bot.get_user(participant.discord_id).send(
                embed=view.initial, view=view
            )
            view.response = out
            views.append(view)

        # Create a list of tasks to wait for the participants to pick a card
        # TODO: consider using asyncio.gather -> collect responses
        pick_tasks = [
            asyncio.wait_for(view.pick_event.wait(), timeout=settings.seconds_per_pick)
            for view in views
        ]

        # Wait for all tasks to complete or for the timeout to expire
        try:
            await asyncio.gather(*pick_tasks)
        except asyncio.TimeoutError:
            # Handle the timeout error if any of the tasks didn't complete within the specified time
            for view, participant in zip(views, participants):
                if not view.pick_event.is_set():
                    logging.info(
                        f"TIMEOUT - Auto picking for user <{participant.discord_id}>"
                    )
                    await view.auto_pick()
            pass

        # pick selected cards
        for view, participant, pack in zip(views, participants, packs):
            await pack.fetch_related("cards")
            card = pack.cards[view.current_card_index]
            await participant.deck.add(card)
            await pack.cards.remove(card)
            logging.info(
                f"PICK - User <{participant.discord_id}> picked card {card.name} in draft {draft_name}"
            )

            # delete pack if empty
            if (
                len(pack.cards) == 1
            ):  # hacky way to check if pack is empty, but it works
                logging.info(
                    f"DELETE - pack {pack} in draft {draft_name} because it is empty"
                )
                await pack.delete()

        # after all participants have picked
        # - check if draft is finished
        rounds_remaining = (
            settings.packs_per_player * settings.cards_per_pack * len(participants) - 1
        )
        if draft.rounds_completed >= rounds_remaining:
            logging.info(
                f"FINISH - Draft {draft_name} has finished after {draft.rounds_completed+1} rounds"
            )
            draft.status = DraftStatus.FINISHED.value
            await draft.save()

            # TODO: this is just a placeholder for now, need to be prettier, probably needs to be a separate function like 'notify_participants'
            # notify participants that the draft has finished
            message = "The draft has finished! Take your time brewing and let me know with `/submit_deck` (**not here** in DMs!) when you're ready. Here is your cardlist:\n"
            for participant in participants:
                cards = await participant.deck.all()
                deck_string = "\n1 ".join([card.link for card in cards])
                deck_string = "```1 " + deck_string + "```"
                await self.bot.get_user(participant.discord_id).send(
                    message + deck_string
                )

            # notify global channel that draft has finished
            embed = await finished_draft_global_notification.get_notification(draft)
            await self.bot.get_channel(draft.notification_channel_id).send(embed=embed)

            return
        else:

            # increment round counter
            draft.rounds_completed += 1
            await draft.save()

            # run the next draft round
            logging.info(
                f"CONTINUE - Draft {draft_name} is continuing with round {draft.rounds_completed+1}/{rounds_remaining+1}"
            )
            await self.draft_step(draft.name)

    # cleanup worker that deletes drafts that have finished every monday
    @tasks.loop(hours=24)
    async def cleanup_drafts(self):
        """Cleans up drafts that have finished."""
        if datetime.utcnow().weekday() == 0:  # 0 is Monday, 1 is Tuesday, etc.
            logging.info("CLEANUP - Running cleanup_drafts task...")
            drafts = await Draft.filter(status=DraftStatus.FINISHED.value)
            for draft in drafts:
                logging.info(f"CLEANUP - Deleting draft {draft.name}")
                await draft.delete()

    @app_commands.command(name="create_draft")
    async def create_draft(self, interaction: Interaction):
        await interaction.response.defer()

        async def get_answer(question, timeout=60):
            await interaction.user.dm_channel.send(question)
            return await self.bot.wait_for(
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
            draft_max_participants_msg = await get_answer(
                "How many maximum participants?"
            )
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
            (
                open_draft_notification_embed,
                open_draft_notification_view,
            ) = await open_draft_notification.get_notification(
                draft_name=draft_name, interaction=interaction
            )

            await interaction.user.dm_channel.send(
                "Draft created successfully! Other players can join the draft now."
            )
            await interaction.followup.send(
                embed=open_draft_notification_embed, view=open_draft_notification_view
            )

        except:
            logging.exception("Error while creating draft (2/2)")
            await interaction.user.dm_channel.send(
                "Something went wrong during the draft creation process (2/2), please try again."
            )
            return

    @app_commands.command(name="show_all_drafts", description="Show all drafts")
    async def show_all_drafts(self, interaction: Interaction):
        drafts = await Draft.all()
        embed = discord.Embed(title="All drafts", color=EMBED_COLOR)
        for draft in drafts:
            embed.add_field(
                name=draft.name,
                value=f"Status: {draft.status}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="show_draft", description="Show a draft")
    @app_commands.describe(draft_name="The name of the draft you want to show")
    async def show_draft(self, interaction: Interaction, draft_name: str):
        # create draft messages for channel
        (
            open_draft_notification_embed,
            open_draft_notification_view,
        ) = await open_draft_notification.get_notification(
            draft_name=draft_name, interaction=interaction
        )

        await interaction.response.send_message(
            embed=open_draft_notification_embed, view=open_draft_notification_view
        )

    @app_commands.command(name="join_draft", description="Join a draft")
    @app_commands.describe(draft_name="The name of the draft you want to join")
    async def join_draft(self, interaction: Interaction, draft_name: str):
        try:
            response = await user_actions.join_draft(draft_name, interaction.user.id)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        await interaction.response.send_message(response, ephemeral=True)

    @app_commands.command(name="leave_draft", description="Leave a draft")
    @app_commands.describe(draft_name="The name of the draft you want to leave")
    async def leave_draft(self, interaction: Interaction, draft_name: str):
        try:
            response = await user_actions.leave_draft(draft_name, interaction.user.id)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        await interaction.response.send_message(response, ephemeral=True)

    @app_commands.command(name="start_draft", description="Start a draft")
    @app_commands.describe(draft_name="The name of the draft you want to start")
    async def start_draft(self, interaction: Interaction, draft_name: str):
        """Starts a draft."""
        await interaction.response.defer()
        try:
            # set up the draft
            response, draft = await user_actions.start_draft(
                draft_name, interaction.user.id, interaction.channel_id
            )

        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        # send success message
        await interaction.followup.send(response)

        # send a welcoming message to all participants
        seconds_delay = 30
        message = f"""
Welcome to the draft **{draft.name}**! If you're familiar with this format, you can get comfy and grab some tea. The draft will start in {seconds_delay} seconds. If you don't know what this is, here's a quick rundown:

In a Collective draft, players are seated around a table and given a set of packs containing randomized cards from a particular Collective cube. Each player opens a pack, selects one card from it, and then passes the remaining cards to the player on their left. This process is repeated until all the cards in the pack have been selected. The players then open their second pack and repeat the process, this time passing the packs to the right. This continues until all the packs have been opened and all the cards have been selected.

After the draft, players use the cards they have selected to construct a deck, which they will use to play against other players in the draft. The goal is to build a strong, cohesive deck that can effectively utilize the cards you have drafted.

Good luck and have fun!"""

        for participant in draft.participants:
            await self.bot.get_user(participant.discord_id).send(message)

        # delay the start of the draft to give participants time to read the message
        await asyncio.sleep(seconds_delay)

        # run the draft
        await self.draft_step(draft.name)

    @app_commands.command(name="stop_draft", description="Stop a draft")
    @app_commands.describe(draft_name="The name of the draft you want to stop")
    async def stop_draft(self, interaction: Interaction, draft_name: str):
        """Stops a draft."""
        try:
            response, draft = await user_actions.stop_draft(
                draft_name, interaction.user.id
            )
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        await interaction.response.send_message(response, ephemeral=True)

        # inform participants that the draft has been stopped
        await draft.fetch_related("participants")
        message = f"""
The draft **{draft.name}** has been stopped by the host. If you have any questions, please contact the host.\n{', '.join([f" <@{participant.discord_id}>" for participant in draft.participants])}
"""

        await self.bot.get_channel(draft.notification_channel_id).send(message)

    @app_commands.command(
        name="submit_deck",
        description="Submit your decklist after the draft has finished",
    )
    @app_commands.describe(
        decklist="The decklist .txt file you want to submit in the format `1 card name | card link | card uid` per line"
    )
    async def submit_deck(self, interaction: Interaction, decklist: Attachment):
        """Submits a decklist."""
        try:
            response = await user_actions.submit_deck(decklist, interaction.user.id)

        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        # send success message
        await interaction.response.send_message(response, ephemeral=True)

        # check if all decks have been submitted
        participant = await User.get(discord_id=interaction.user.id).prefetch_related(
            "participates_in_draft"
        )
        draft = participant.participates_in_draft
        participants = await draft.participants.all()
        if all([participant.deck_string for participant in participants]):
            # send the decklists to the global channel
            channel = self.bot.get_channel(draft.notification_channel_id)
            await channel.send("All decks have been submitted, Here are the decklists:")
            for participant in participants:
                # if the decklist is too long, send it as a file
                if len(participant.deck_string) > 2000:
                    with open("Data/decklist.txt", "w") as f:
                        f.write(participant.deck_string)
                    await channel.send(
                        file=discord.File(f"Data/decklist.txt"),
                        content=f"deck by <@{participant.discord_id}>",
                    )
                else:
                    await channel.send(
                        f"deck by <@{participant.discord_id}>\n"
                        + "```"
                        + participant.deck_string
                        + "```"
                    )

            # delete the draft
            logging.info(f"DELETE - Draft {draft.name} has been deleted")
            await draft.delete()


async def setup(bot):  # an extension must have a setup function
    await bot.add_cog(DraftCog(bot))  # adding a cog
