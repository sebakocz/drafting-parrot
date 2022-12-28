from tortoise.exceptions import DoesNotExist

from Database.Models.draft import Draft, DraftStatus
from Database.draft_setup import get_or_create_user_by_discord_id


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
