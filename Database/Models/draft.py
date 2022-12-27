from discord.ext import tasks
from enum import Enum

from tortoise.fields import ReverseRelation
from tortoise.models import Model
from tortoise import fields

from Database.Models.card import Card
from Database.Models.settings import Settings


class PickType(Enum):
    """Pick type enum."""

    SINGLETON = "singleton"
    BLUEPRINT = "blueprint"


class DraftStatus(Enum):
    """Draft status enum."""

    PREPARING = "preparing"
    RUNNING = "running"
    FINISHED = "finished"


class Draft(Model):

    name = fields.CharField(max_length=30, unique=True)
    description = fields.TextField()
    settings: fields.OneToOneRelation["Settings"]
    status = fields.CharField(max_length=30, default=DraftStatus.PREPARING.value)
    participants = fields.ForeignKeyRelation["User"]
    owner = fields.ManyToManyField("models.User", related_name="owner_of_drafts")
    cards: ReverseRelation[Card]
    packs = fields.ForeignKeyRelation["Pack"]
    max_participants = fields.IntField(min_value=4, max_value=10)
    rounds_completed = fields.IntField(default=0)
    notification_channel_id = fields.BigIntField(null=True)

    async def delete(self, *args, **kwargs):
        # clear participants' deck_strings
        await self.fetch_related("participants")
        for participant in self.participants:
            participant.deck_string = None
            await participant.save()

        await super().delete(*args, **kwargs)
