class DetailsMixin:
    def __init__(self):
        # self.price: float = 0
        self.free: float = 0
        self.in_orders: float = 0
        self.amount: float = 0
        self.cost_now: float = 0

    def update_details(self):
        pass

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
