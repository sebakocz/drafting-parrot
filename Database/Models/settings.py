from tortoise import fields, Model

class Settings(Model):
    """Settings model."""

    pick_type = fields.CharField(max_length=30)
    packs_per_player = fields.IntField()
    cards_per_pack = fields.IntField()
    seconds_per_pick = fields.IntField()
    draft: fields.OneToOneRelation["Draft"] = fields.OneToOneField(
        "models.Draft", related_name="settings", on_delete=fields.CASCADE
    )

    def __str__(self):
        return f"{self.pick_type} - {self.packs_per_player} - {self.cards_per_pack} - {self.seconds_per_pick}"