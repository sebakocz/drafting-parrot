from random import shuffle

from tortoise.exceptions import DoesNotExist

from Database.Models.draft import Draft, DraftStatus
from Database.Models.pack import Pack
from Database.draft_setup import get_or_create_user_by_discord_id
from constants import MIN_PARTICIPANTS


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
    if len(
        draft.participants
    ) * draft.settings.packs_per_player * draft.settings.cards_per_pack > len(
        draft.cards
    ):
        raise ValueError(
            "Draft settings are not valid. Make sure you have enough cards for the draft."
        )

    # create cards for packs
    copied_cardpool = await draft.cards.all()
    shuffle(copied_cardpool)
    pack_cards = [
        copied_cardpool[i : i + draft.settings.cards_per_pack]
        for i in range(
            0,
            draft.settings.cards_per_pack
            * draft.settings.packs_per_player
            * len(draft.participants),
            draft.settings.cards_per_pack,
        )
    ]

    # create packs
    for cards in pack_cards:
        new_pack = await Pack.create(draft=draft)
        await new_pack.cards.add(*cards)
        await new_pack.save()

    draft.status = DraftStatus.RUNNING.value
    draft.notification_channel_id = channel_id
    await draft.save()

    return "Draft started successfully. Have fun!", draft
