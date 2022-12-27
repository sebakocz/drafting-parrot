from tortoise import Model, fields


class Card(Model):
    """Card model."""

    name = fields.CharField(max_length=30)
    link = fields.CharField(max_length=90)
    draft: fields.ForeignKeyRelation["Draft"] = fields.ForeignKeyField(
        "models.Draft", related_name="cards", on_delete=fields.CASCADE, null=True
    )

    class Meta:
        unique_together = ("draft", "link")
