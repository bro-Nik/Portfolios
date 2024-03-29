from portfolio_tracker.general_functions import find_by_attr


class DetailsMixin:
    def __init__(self):
        self.free: float = 0
        self.in_orders: float = 0
        self.amount: float = 0
        self.cost_now: float = 0

    @property
    def profit(self):
        return self.cost_now - self.amount

    @property
    def profit_percent(self):
        if self.profit and self.amount:
            return abs(round(self.profit / self.amount * 100))

    @property
    def color(self):
        round_profit = round(self.profit)
        if round_profit > 0:
            return 'text-green'
        if round_profit < 0:
            return 'text-red'

    def share_of_portfolio(self, parent_amount):
        if self.amount < 0 or not parent_amount:
            return 0
        return self.amount / parent_amount * 100


class AssetsMixin:
    def get_asset(self, ticker_id: str | None):
        if ticker_id:
            return find_by_attr(self.assets, 'ticker_id', ticker_id)
