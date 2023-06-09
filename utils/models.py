from os import getenv
from typing import Any

from tortoise import fields
from tortoise.models import Model


class BaseModel(Model):
    class Meta:
        abstract = True


class CryptoModel(BaseModel):
    class Meta:
        indexes = ["id"]

    id = fields.IntField(pk=True)
    tag = fields.CharField(max_length=3)
    name = fields.CharField(max_length=32)
    price = fields.FloatField()
    changes = fields.IntField(default=10)


class CryptoHistoryModel(BaseModel):
    class Meta:
        indexes = ["id", "crypto_id"]

    id = fields.IntField(pk=True)
    crypto_id = fields.IntField()
    price = fields.FloatField()
    created_at = fields.DatetimeField(auto_now_add=True)


class EconomyModel(BaseModel):
    class Meta:
        indexes = ["id", "user_id"]

    id = fields.IntField(pk=True)
    user_id = fields.IntField()
    balance = fields.IntField(default=float(getenv("STARTING_BALANCE")))
    crypto_balance = fields.JSONField(default={})
