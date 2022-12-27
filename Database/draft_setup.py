import logging

from Database.Models.card import Card
from Database.Models.draft import Draft, PickType
from Database.Models.settings import Settings
from Database.Models.user import User


async def get_cards_from_data(cards: list, draft: Draft) -> list:
    """Get cards from object."""
    new_cards = []
    for card in cards:
        card = await Card.create(name=card["name"], link=card["link"], draft=draft)
        await card.save()
        new_cards.append(card)
    return new_cards


async def create_draft(
    owner_discord_id: int,
    name: str,
    description: str,
    pick_type: PickType,
    packs_per_player: int,
    cards_per_pack: int,
    seconds_per_pick: int,
    max_participants: int,
) -> Draft:
    owner = await get_or_create_user_by_discord_id(owner_discord_id)

    new_draft = await Draft.create(
        name=name,
        description=description,
        max_participants=max_participants,
    )
    await new_draft.owner.add(owner)
    await new_draft.save()

    settings = Settings(
        pick_type=pick_type.value,
        packs_per_player=packs_per_player,
        cards_per_pack=cards_per_pack,
        seconds_per_pick=seconds_per_pick,
        draft=new_draft,
    )
    await settings.save()

    return new_draft


async def get_or_create_user_by_discord_id(discord_id: int) -> User:
    user = await User.get_or_none(discord_id=discord_id)

    if not user:
        user = User(discord_id=discord_id)
        await user.save()

    return user
