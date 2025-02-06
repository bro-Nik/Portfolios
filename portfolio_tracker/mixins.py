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
