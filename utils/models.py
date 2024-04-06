from os import getenv
from typing import Optional

import unbelievaboat
from tortoise import fields
from tortoise.models import Model


client = unbelievaboat.Client(getenv("UNBELIEVABOAT_API_TOKEN"))


class MissingBalance(Exception):
    pass


class BaseModel(Model):
    id = fields.IntField(pk=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        abstract = True


class CryptoModel(BaseModel):
    class Meta:
        indexes = ["id"]

    tag = fields.CharField(max_length=3)
    name = fields.CharField(max_length=32)
    price = fields.FloatField()
    changes = fields.IntField(default=10)


class CryptoHistoryModel(BaseModel):
    class Meta:
        indexes = ["id", "crypto_id"]

    crypto_id = fields.IntField()
    price = fields.FloatField()


class EconomyModel(BaseModel):
    class Meta:
        indexes = ["id", "user_id"]

    user_id = fields.IntField()
    guild_id = fields.IntField()
    crypto_balance = fields.JSONField(default={})
    balance: Optional[int] = None

    async def fetch_balance(self) -> None:
        balance = await client.get_user_balance(self.guild_id, self.user_id)
        self.balance = balance.cash or 0

    async def update_balance(self, reason: Optional[str] = None) -> None:
        if self.balance is None:
            raise MissingBalance(
                "You have to use EconomyModel.fetch_balance() before committing changes."
            )
        await client.set_user_balance(
            self.guild_id, self.user_id, {"cash": self.balance}, reason
        )
