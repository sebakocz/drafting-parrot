import asyncio
import logging
import platform

import pytest

from Components import user_actions
from Database import database
from Database.Models.card import Card
from Database.Models.draft import PickType, DraftStatus, Draft
from Database.Models.settings import Settings
from Database.Models.user import User
from Database.draft_setup import create_draft, get_cards_from_data, get_or_create_user_by_discord_id
from Tests.constants import OUTPUT_CARD_OBJECTS, INPUT_FILE_LINES, DRAFT_OPTIONS, DRAFT_OPTIONS_TWO, \
    INPUT_FILE_LINES_LONG, CARDS_LIST_LONG
from Utils.collective_api import get_card_data

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# TODO: failure test cases
# TODO: test for cardpool with no cards
# TODO: test for uid-like strings that is not an actual card
# TODO: test for gibberish strings, probably covered by above


@pytest.mark.skip
async def test_can_get_cardpool():
    """Test if we can get a cardpool from the collective api."""
    result = await get_card_data(INPUT_FILE_LINES)
    assert result == OUTPUT_CARD_OBJECTS

@pytest.fixture(autouse=True)
async def initialize_database():
    """Create a database connection for testing."""
    logging.info("Creating test database")
    await database.init("Tests/test_database.db")
    yield
    logging.info("Closing test database")
    await database.Tortoise.close_connections()

    # use to delete db file
    await database.Tortoise._drop_databases()


# @pytest.mark.skip
async def test_can_create_draft():

    draft = await create_draft(**DRAFT_OPTIONS)

    cards = await get_cards_from_data(OUTPUT_CARD_OBJECTS, draft)
    assert len(cards) == 9

    await draft.fetch_related("cards", "settings", "participants", "owner")


    assert draft is not None
    assert draft.name == DRAFT_OPTIONS["name"]
    assert draft.description == DRAFT_OPTIONS["description"]
    assert draft.settings.pick_type == DRAFT_OPTIONS["pick_type"].value
    assert draft.settings.packs_per_player == DRAFT_OPTIONS["packs_per_player"]
    assert draft.settings.cards_per_pack == DRAFT_OPTIONS["cards_per_pack"]
    assert draft.settings.seconds_per_pick == DRAFT_OPTIONS["seconds_per_pick"]
    assert len(draft.cards) == len(INPUT_FILE_LINES)
    assert len(draft.owner) >= 1, "Should have at least one owner"

    await draft.delete()

    assert len(await Card.filter(draft=draft)) == 0, "Related cards should be deleted"
    assert await Settings.get_or_none(draft=draft) is None, "Related settings should be deleted"
    assert await User.get_or_none(discord_id=DRAFT_OPTIONS["owner_discord_id"]) is not None, "Owner should not be deleted"


# @pytest.mark.skip
async def test_can_join_draft():
    draft = await create_draft(**DRAFT_OPTIONS)

    assert draft.status == DraftStatus.PREPARING.value, "Draft should be preparing"

    user1_id = 123
    user2_id = 456
    user3_id = 789
    user4_id = 101112

    # for failure test cases
    user5_id = 131415

    await user_actions.join_draft(draft.name, user1_id)
    await user_actions.join_draft(draft.name, user2_id)
    await user_actions.join_draft(draft.name, user3_id)
    await user_actions.join_draft(draft.name, user4_id)

    with pytest.raises(ValueError):
        await user_actions.join_draft(draft.name, user5_id), "Should not be able to join draft due to max players"

    await draft.fetch_related("participants")

    assert len(draft.participants) == 4, "Should have 4 participants"

    await draft.delete()

    assert await User.get_or_none(discord_id=user1_id) is not None, "User1 should not be deleted"
    assert await User.get_or_none(discord_id=user2_id) is not None, "User2 should not be deleted"
    assert await User.get_or_none(discord_id=user3_id) is not None, "User3 should not be deleted"


# @pytest.mark.skip
async def test_can_join_and_create_multiple_drafts():
    draft1 = await create_draft(**DRAFT_OPTIONS)

    draft2 = await create_draft(**DRAFT_OPTIONS_TWO)

    user_id = 123

    await user_actions.join_draft(draft1.name, user_id)

    await draft1.fetch_related("participants")
    await draft2.fetch_related("participants")

    assert len(draft1.participants) == 1, "Should have 1 participant"
    assert len(draft2.participants) == 0, "Should have 0 participants"

    await draft1.delete()
    await draft2.delete()


# @pytest.mark.skip
async def test_can_leave_draft():
    user_id = 123

    with pytest.raises(ValueError):
        await user_actions.leave_draft("non-existant-draft", user_id), "Should not be able to leave draft that does not exist"

    draft = await create_draft(**DRAFT_OPTIONS)

    await user_actions.join_draft(draft.name, user_id)

    await user_actions.leave_draft(draft.name, user_id)

    with pytest.raises(ValueError):
        await user_actions.leave_draft(draft.name, user_id), "Should not be able to leave draft that user is not in"

    await draft.fetch_related("participants")
    assert len(draft.participants) == 0, "Should have 0 participants"
    assert await User.get_or_none(discord_id=user_id) is not None, "User should not be deleted"
    assert draft.status == DraftStatus.PREPARING.value, "Draft should be preparing"

    await draft.delete()


# @pytest.mark.skip
async def test_can_start_draft():

    draft = await create_draft(**DRAFT_OPTIONS)

    await get_cards_from_data(CARDS_LIST_LONG, draft)

    participants = [
        await get_or_create_user_by_discord_id(DRAFT_OPTIONS["owner_discord_id"]),
        await get_or_create_user_by_discord_id(456),
        await get_or_create_user_by_discord_id(789),
        # can alternate between 3 and 4 players for better testing, just uncomment the next line
        # await get_or_create_user_by_discord_id(101112),
    ]

    for participant in participants:
        await user_actions.join_draft(draft.name, participant.discord_id)

    with pytest.raises(ValueError):
        await user_actions.start_draft(draft.name, participants[1].discord_id, 123), "Should not be able to start draft if not owner"

    await user_actions.start_draft(draft.name, participants[0].discord_id, 123)

    draft = await Draft.get(name=draft.name)
    await draft.fetch_related("participants", "settings", "packs__cards")


    assert draft.status == DraftStatus.RUNNING.value, "Draft should be running"
    assert len(draft.packs) == len(participants) * DRAFT_OPTIONS["packs_per_player"], "Should have <players * pack_per_player> total packs"
    assert all(len(pack.cards) == draft.settings.cards_per_pack for pack in draft.packs), "Packs should have cards"

    await draft.delete()
