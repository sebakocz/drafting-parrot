import io
import logging
from random import shuffle

from discord import Interaction, Attachment
from tortoise.exceptions import DoesNotExist

from Components.constants import MIN_PARTICIPANTS
from Database.Models.draft import Draft, DraftStatus
from Database.Models.pack import Pack
from Database.Models.user import User
from Database.draft_setup import get_or_create_user_by_discord_id


async def join_draft(draft_name: str, user_discord_id: int):
    """Handle join draft interaction."""

    try:
        draft = await Draft.get(name=draft_name).prefetch_related("participants")
    except DoesNotExist:
        raise ValueError("Draft does not exist.")

    if draft.status != DraftStatus.PREPARING.value:
        raise ValueError("Draft is not accepting participants anymore.")

    user = await get_or_create_user_by_discord_id(user_discord_id)

    if user in draft.participants:
        raise ValueError("You already joined this draft.")

    if len(draft.participants) >= draft.max_participants:
        raise ValueError("Draft is full.")

    user.participates_in_draft = draft
    await user.save()

    return "You joined the draft successfully."


async def leave_draft(draft_name: str, user_discord_id: int):
    """Handle leave draft interaction."""

    try:
        draft = await Draft.get(name=draft_name).prefetch_related("participants")
    except DoesNotExist:
        raise ValueError("Draft does not exist.")

    if draft.status != DraftStatus.PREPARING.value:
        raise ValueError("You can't leave the draft anymore.")

    user = await get_or_create_user_by_discord_id(user_discord_id)

    if user not in draft.participants:
        raise ValueError("You are not part of this draft.")

    user.participates_in_draft = None
    await user.save()

    return "You left the draft successfully."


async def start_draft(draft_name: str, user_discord_id: int, channel_id: int):
    """Handle start draft interaction."""

    try:
        draft = await Draft.get(name=draft_name)
    except DoesNotExist:
        raise ValueError("Draft does not exist.")

    await draft.fetch_related("settings", "participants", "packs", "cards", "owner")

    user = await get_or_create_user_by_discord_id(user_discord_id)

    if user not in draft.owner:
        raise ValueError("You are not the owner of this draft.")

    if len(draft.participants) < MIN_PARTICIPANTS:
        raise ValueError("Draft does not have enough participants.")

    if draft.status != DraftStatus.PREPARING.value:
        raise ValueError("Draft already started.")

    # check if settings make sense
    # current players * packs per player * cards per pack <= total cards
    if len(draft.participants) * draft.settings.packs_per_player * draft.settings.cards_per_pack > len(draft.cards):
        raise ValueError("Draft settings are not valid. Make sure you have enough cards for the draft.")

    # create cards for packs
    copied_cardpool = await draft.cards.all()
    shuffle(copied_cardpool)
    pack_cards = [copied_cardpool[i:i + draft.settings.cards_per_pack] for i in range(0, draft.settings.cards_per_pack * draft.settings.packs_per_player * len(draft.participants), draft.settings.cards_per_pack)]

    # create packs
    for cards in pack_cards:
        new_pack = await Pack.create(draft=draft)
        await new_pack.cards.add(*cards)
        await new_pack.save()

    draft.status = DraftStatus.RUNNING.value
    draft.notification_channel_id = channel_id
    await draft.save()

    return "Draft started successfully. Have fun!", draft


async def stop_draft(draft_name:str, user_discord_id: int):
    """Handle stop draft interaction."""

    try:
        draft = await Draft.get(name=draft_name)
    except DoesNotExist:
        raise ValueError("Draft does not exist.")

    await draft.fetch_related("owner")

    user = await get_or_create_user_by_discord_id(user_discord_id)

    if user not in draft.owner:
        raise ValueError("You are not the owner of this draft.")

    if draft.status == DraftStatus.PREPARING.value:
        raise ValueError("Draft has not started yet.")

    if draft.status == DraftStatus.FINISHED.value:
        raise ValueError("Draft already finished.")

    draft.status = DraftStatus.FINISHED.value
    await draft.save()

    return "Draft stopped successfully.", draft


async def submit_deck(cardlist: Attachment, user_discord_id: int):
    """Handle submit deck interaction."""

    try:
        participant = await User.get(discord_id=user_discord_id)
    except DoesNotExist:
        raise ValueError("You are not part of a draft.")
    await participant.fetch_related("participates_in_draft")
    draft = participant.participates_in_draft

    if not draft:
        raise ValueError("You are not part of a draft.")

    if draft.status != DraftStatus.FINISHED.value:
        raise ValueError("Draft did not finish yet. You can't submit your decklist yet.")

    # check if decklist is set
    if participant.deck_string:
        raise ValueError("You already submitted your decklist.")

    # check if decklist is valid
    if not cardlist.filename.endswith(".txt"):
        raise ValueError("Decklist must be a .txt file.")

    # ignore giagantic files
    if cardlist.size > 100000:
        raise ValueError("Decklist is too big.")

    # check if each line
    # - starts with '1x', '2x', '3x'
    # - has a space after the number
    # - has a card name, card link or card uid (currently just checks if not empty, no actual validation)
    # - or is a comment -> starts with '#'
    lines = await cardlist.read()
    lines = lines.decode("utf-8").splitlines()
    for line in lines:
        if line.startswith("#"):
            continue
        if not line.startswith(("1 ", "2 ", "3 ")):
            raise ValueError("Invalid decklist. Each non-comment (#) line must start with '1', '2' or '3'.")
        if not line[3:].strip():
            raise ValueError("Invalid decklist. Each non-comment (#) line must have a card name, card link or card uid.")

    # save decklist
    participant.deck_string = "\n".join(lines)
    await participant.save()

    return "Decklist submitted successfully."