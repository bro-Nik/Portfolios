from __future__ import annotations

from flask_login import current_user

from ..models import DetailsMixin


class Portfolios(DetailsMixin):
    """Класс объединяет все портфели пользователя."""
    def __init__(self):
        super().__init__()
        for portfolio in current_user.portfolios:
            portfolio.update_price()
            self.amount += portfolio.amount
            self.cost_now += portfolio.cost_now
            self.in_orders += portfolio.in_orders
