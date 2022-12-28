from tortoise.exceptions import DoesNotExist

from Database.Models.draft import Draft, DraftStatus
from Database.draft_setup import get_or_create_user_by_discord_id


async def stop_draft(draft_name: str, user_discord_id: int):
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
