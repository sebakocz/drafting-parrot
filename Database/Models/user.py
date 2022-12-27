import logging

from tortoise.models import Model
from tortoise import fields


class User(Model):

    discord_id = fields.IntField(max_length=30, unique=True)
    owner_of_drafts = fields.ManyToManyRelation["Draft"]
    participates_in_draft = fields.ForeignKeyField(
        "models.Draft",
        related_name="participants",
        null=True,
        on_delete=fields.SET_NULL,
    )
    deck = fields.ManyToManyField("models.Card", related_name="users")
    deck_string = fields.TextField(null=True)
