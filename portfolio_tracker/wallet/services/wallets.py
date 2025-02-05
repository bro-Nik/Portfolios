from __future__ import annotations
from typing import TYPE_CHECKING

from ...models import DetailsMixin

if TYPE_CHECKING:
    from portfolio_tracker.user.models import User


class Wallets(DetailsMixin):
    def __init__(self, user: User):
        super().__init__()
        for wallet in user.wallets:
            wallet.service.update_price()
            self.cost_now += wallet.cost_now
            self.buy_orders += wallet.buy_orders
