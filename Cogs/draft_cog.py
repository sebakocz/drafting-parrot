# cog for starting and running a draft
import asyncio
import logging
from datetime import datetime

import discord
from discord import app_commands, Interaction, Attachment
from discord.ext import commands, tasks

import Actions.join_draft_act
import Actions.leave_draft_act
import Actions.start_draft_act
import Actions.stop_draft_act
import Actions.submit_deck_act
from Actions import create_draft_act

from Database.Models.draft import Draft, DraftStatus
from Database.Models.pack import Pack
from Database.Models.user import User
from Messages import (
    finished_draft_global_msg,
    player_pick_msg,
    show_all_drafts_msg,
    open_draft_msg,
)


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
            message = await player_pick_msg.get_message(
                pack,
                f"{int((draft.rounds_completed) / settings.cards_per_pack) +1}/{settings.packs_per_player}",
            )
            out = await self.bot.get_user(participant.discord_id).send(**message)
            message["view"].response = out
            views.append(message["view"])

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
            message = "The draft has finished! Take your time brewing and let me know with `/submit_deck` (**not in DMs!**) when you're ready. Here is your cardlist:\n"
            for participant in participants:
                cards = await participant.deck.all()
                deck_string = "\n1 ".join([card.link for card in cards])
                deck_string = "```1 " + deck_string + "```"
                await self.bot.get_user(participant.discord_id).send(
                    message + deck_string
                )

            # notify global channel that draft has finished
            message = await finished_draft_global_msg.get_message(draft)
            await self.bot.get_channel(draft.notification_channel_id).send(**message)

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
        await create_draft_act.create_draft_dis(interaction)

    @app_commands.command(name="show_all_drafts", description="Show all drafts")
    async def show_all_drafts(self, interaction: Interaction):
        message = await show_all_drafts_msg.get_message()
        await interaction.response.send_message(**message)

    @app_commands.command(name="show_draft", description="Show a draft")
    @app_commands.describe(draft_name="The name of the draft you want to show")
    async def show_draft(self, interaction: Interaction, draft_name: str):
        # create draft messages for channel
        message = await open_draft_msg.get_message(
            draft_name=draft_name, interaction=interaction
        )

        await interaction.response.send_message(**message)

    @app_commands.command(name="join_draft", description="Join a draft")
    @app_commands.describe(draft_name="The name of the draft you want to join")
    async def join_draft(self, interaction: Interaction, draft_name: str):
        try:
            response = await Actions.join_draft_act.join_draft(
                draft_name, interaction.user.id
            )
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        await interaction.response.send_message(response, ephemeral=True)

    @app_commands.command(name="leave_draft", description="Leave a draft")
    @app_commands.describe(draft_name="The name of the draft you want to leave")
    async def leave_draft(self, interaction: Interaction, draft_name: str):
        try:
            response = await Actions.leave_draft_act.leave_draft(
                draft_name, interaction.user.id
            )
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
            response, draft = await Actions.start_draft_act.start_draft(
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
            response, draft = await Actions.stop_draft_act.stop_draft(
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
            response = await Actions.submit_deck_act.submit_deck(
                decklist, interaction.user.id
            )

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
