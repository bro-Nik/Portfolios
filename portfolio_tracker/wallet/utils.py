from __future__ import annotations

from flask_login import current_user

from ..models import DetailsMixin


class Wallets(DetailsMixin):
    def __init__(self):
        super().__init__()
        for wallet in current_user.wallets:
            wallet.update_price()
            self.cost_now += wallet.cost_now
            self.in_orders += wallet.in_orders
            self.free += wallet.free
