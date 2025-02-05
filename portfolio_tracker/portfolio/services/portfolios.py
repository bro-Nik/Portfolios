from __future__ import annotations
from typing import TYPE_CHECKING

from ..models import DetailsMixin

if TYPE_CHECKING:
    from portfolio_tracker.user.models import User

class Portfolios(DetailsMixin):
    """Класс объединяет все портфели пользователя."""

    def __init__(self, user: User):
        super().__init__()

        for portfolio in user.portfolios:
            portfolio.service.update_info()

            self.amount += portfolio.amount
            self.buy_orders += portfolio.buy_orders
            self.invested += portfolio.amount if portfolio.amount > 0 else 0
            self.cost_now += portfolio.cost_now
