from tortoise.exceptions import DoesNotExist

from Database.Models.draft import Draft, DraftStatus
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
