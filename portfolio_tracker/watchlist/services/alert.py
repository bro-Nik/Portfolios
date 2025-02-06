from portfolio_tracker.portfolio.models import Transaction
from portfolio_tracker.portfolio.repository import TickerRepository
from ..models import Alert
from ..models import Watchlist
from ..repository import AlertRepository


class AlertService:

    def __init__(self, alert: Alert) -> None:
        self.alert = alert

    def edit(self, form) -> None:
        self.alert.price = float(form.get('price', 0))
        self.alert.price_ticker_id = form.get('price_ticker_id', '')
        self.alert.price_ticker = TickerRepository.get(self.alert.price_ticker_id)

        self.alert.price_usd = self.alert.price / self.alert.price_ticker.price
        self.alert.comment = form['comment']

        asset_price = self.alert.watchlist_asset.ticker.price
        self.alert.type = 'down' if asset_price >= self.alert.price_usd else 'up'

        AlertRepository.save(self.alert)

    def turn_off(self) -> None:
        if not self.alert.transaction_id:
            self.alert.status = 'off'

    def turn_on(self) -> None:
        if self.alert.transaction_id and self.alert.status != 'on':
            self.alert.transaction_id = None
            self.alert.asset_id = None
        self.alert.status = 'on'

    def delete(self) -> None:
        if not self.alert.transaction_id:
            AlertRepository.delete(self.alert)

    def convert_order_to_transaction(self):
        self.alert.transaction.convert_order_to_transaction()


def update_alert(alert: Alert | None, transaction: Transaction) -> None:
    if not transaction.order and alert:
        alert.transaction_id = None
        alert.service.delete()
    elif transaction.order:
        if not alert:
            watchlist = Watchlist()
            watchlist_asset = watchlist.service.get_asset(transaction.ticker_id)
            if not watchlist_asset:
                watchlist_asset = watchlist.service.create_asset(transaction.ticker_id, save=True)
                transaction.portfolio.user.watchlist.append(watchlist_asset)
            alert = watchlist_asset.service.create_alert()
            watchlist_asset.alerts.append(alert)

        alert.price = transaction.price
        alert.price_usd = transaction.price_usd
        alert.price_ticker_id = transaction.ticker2_id
        alert.date = transaction.date
        alert.transaction_id = transaction.id
        alert.asset_id = transaction.portfolio_asset.id
        alert.comment = transaction.comment

        alert.type = ('down' if transaction.base_ticker.price >= alert.price_usd
                        else 'up')
