from discord import Attachment
from tortoise.exceptions import DoesNotExist

from Database.Models.draft import DraftStatus
from Database.Models.user import User


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
        raise ValueError(
            "Draft did not finish yet. You can't submit your decklist yet."
        )

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
            raise ValueError(
                "Invalid decklist. Each non-comment (#) line must start with '1', '2' or '3'."
            )
        if not line[3:].strip():
            raise ValueError(
                "Invalid decklist. Each non-comment (#) line must have a card name, card link or card uid."
            )

    # save decklist
    participant.deck_string = "\n".join(lines)
    await participant.save()

    return "Decklist submitted successfully."
