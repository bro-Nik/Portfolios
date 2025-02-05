from portfolio_tracker.general_functions import from_user_datetime
from portfolio_tracker.portfolio.models import OtherBody
from portfolio_tracker.portfolio.repository import BodyRepository, TickerRepository


class OtherBodyService:

    def __init__(self, body: OtherBody) -> None:
        self.body = body

    def edit(self, form: dict) -> None:
        body = self.body

        body.name = form['name']
        body.date = from_user_datetime(form['date'])
        body.comment = form['comment']
        body.amount = float(form['amount'])
        body.cost_now = float(form['cost_now'])

        body.amount_ticker_id = form['amount_ticker_id']
        body.cost_now_ticker_id = form['cost_now_ticker_id']

        amount_ticker = TickerRepository.get(body.amount_ticker_id)
        cost_now_ticker = TickerRepository.get(body.cost_now_ticker_id)
        if amount_ticker and cost_now_ticker:
            body.amount_usd = body.amount * amount_ticker.price
            body.cost_now_usd = body.cost_now * cost_now_ticker.price

        self.update_dependencies()
        BodyRepository.save(self.body)

    def update_dependencies(self, param: str = '') -> None:
        # Направление сделки (direction)
        d = -1 if param == 'cancel' else 1

        self.asset.amount += self.asset.amount_usd * d
        self.asset.cost_now += self.asset.cost_now_usd * d

    def delete(self) -> None:
        self.update_dependencies('cancel')
        BodyRepository.delete(self.body)
