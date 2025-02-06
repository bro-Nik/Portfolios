from portfolio_tracker.general_functions import from_user_datetime
from portfolio_tracker.portfolio.models import OtherTransaction
from portfolio_tracker.portfolio.repository import OtherTransactionRepository, TickerRepository


class OtherTransactionService:

    def __init__(self, transaction: OtherTransaction) -> None:
        self.transaction = transaction

    def edit(self, form: dict) -> None:
        t = self.transaction

        t.date = from_user_datetime(form['date'])
        t.comment = form['comment']
        t.type = form['type']
        t_type = 1 if t.type == 'Profit' else -1
        t.amount_ticker_id = form['amount_ticker_id']
        t.amount = float(form['amount']) * t_type

        amount_ticker = TickerRepository.get(t.amount_ticker_id)
        if amount_ticker:
            t.amount_usd = t.amount * t.amount_ticker.price

    def update_dependencies(self, param: str = '') -> None:
        # Направление сделки (direction)
        d = -1 if param == 'cancel' else 1

        t = self.transaction
        t.asset.cost_now += t.amount_usd * d

    def delete(self) -> None:
        self.update_dependencies('cancel')
        OtherTransactionRepository.delete(self.transaction)
