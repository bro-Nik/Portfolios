class DetailsMixin:
    def __init__(self):
        self.price: float = 0
        self.free: float = 0
        self.in_orders: float = 0
        self.profit: float = 0
        self.amount: float = 0
        self.cost_now: float = 0
        self.color: str = ''
        self.profit_percent: str = ''

    def update_details(self):
        self.profit = self.cost_now - self.amount

        round_profit = round(self.profit)
        if round_profit > 0:
            self.color = 'text-green'
        elif round_profit < 0:
            self.color = 'text-red'

        if self.profit and self.amount:
            self.profit_percent = abs(int(self.profit / self.amount * 100))
