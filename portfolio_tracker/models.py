from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from .general_functions import find_by_attr

if TYPE_CHECKING:
    pass


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True)


class DetailsMixin:
    def __init__(self):
        self.cost_now = 0
        self.amount = 0
        self.buy_orders = 0
        self.free = 0
        self.invested = 0

    @property
    def profit(self):
        return self.cost_now - self.amount


class TransactionsMixin:
    def get_transaction(self, transaction_id: str | int | None):
        return find_by_attr(self.transactions, 'id', transaction_id)


class AssetMixin:
    @property
    def is_empty(self) -> bool:
        return not (self.transactions or self.comment)

    @property
    def price(self) -> float:
        return self.ticker.price

    @property
    def cost_now(self) -> float:
        return self.quantity * self.price

    @property
    def free(self) -> float:
        return self.quantity - self.sell_orders
