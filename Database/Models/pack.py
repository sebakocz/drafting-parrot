from tortoise import Model, fields


class Pack(Model):
    """Pack model."""

    cards = fields.ManyToManyField("models.Card", related_name="packs")
    draft = fields.ForeignKeyField("models.Draft", related_name="packs")
