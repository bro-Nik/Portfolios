from .general_functions import find_by_attr


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
    def get_transaction(self, transaction_id: str | int | None
                        ):
        return find_by_attr(self.transactions, 'id', transaction_id)
