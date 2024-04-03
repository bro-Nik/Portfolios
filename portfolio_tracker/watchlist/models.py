from __future__ import annotations
from typing import List
from datetime import datetime, timezone

from flask_login import current_user
from sqlalchemy.orm import Mapped

from ..app import db
from ..general_functions import find_by_attr
from ..portfolio.models import Ticker


class WatchlistAsset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey('user.id'))
    ticker_id: str = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    comment: str = db.Column(db.Text)

    # Relationships
    ticker: Mapped[Ticker] = db.relationship('Ticker', uselist=False)
    alerts: Mapped[List[Alert]] = db.relationship(
        'Alert', backref=db.backref('watchlist_asset', lazy=True))

    def edit(self, form: dict) -> None:
        comment = form.get('comment')
        if comment is not None:
            self.comment = comment

    @property
    def is_empty(self) -> bool:
        return not (self.alerts or self.comment)

    @property
    def price(self):
        return self.ticker.price

    def get_alert(self, alert_id: int | str | None) -> Alert | None:
        return find_by_attr(self.alerts, 'id', alert_id)

    def create_alert(self) -> Alert:
        alert = Alert()
        return alert

    def delete_if_empty(self) -> None:
        for alert in self.alerts:
            if not alert.transaction_id:
                self.alerts.remove(alert)
                alert.delete()
        if self.is_empty:
            self.delete()

    def delete(self) -> None:
        for alert in self.alerts:
            alert.delete()
        db.session.delete(self)


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date: datetime = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    asset_id: int | None = db.Column(db.Integer, db.ForeignKey('asset.id'))
    watchlist_asset_id: int = db.Column(db.Integer,
                                        db.ForeignKey('watchlist_asset.id'))
    price: float = db.Column(db.Float)
    price_usd: float = db.Column(db.Float)
    price_ticker_id: str = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    type: str = db.Column(db.String(24))
    comment: str = db.Column(db.String(1024))
    status: str = db.Column(db.String(24), default='on')
    transaction_id: int | None = db.Column(db.Integer,
                                           db.ForeignKey('transaction.id'))

    # Relationships
    asset: Mapped[Asset] = db.relationship(
        'Asset', backref=db.backref('alerts', lazy=True))
    transaction: Mapped[Transaction] = db.relationship(
        'Transaction', backref=db.backref('alert', uselist=False))
    price_ticker: Mapped[Ticker] = db.relationship('Ticker', uselist=False)

    def edit(self, form: dict) -> None:
        self.price = float(form['price'])
        self.price_ticker_id = form['price_ticker_id']
        self.price_ticker = Ticker.get(self.price_ticker_id)

        self.price_usd = self.price / self.price_ticker.price
        self.comment = form['comment']

        asset_price = self.watchlist_asset.ticker.price
        self.type = 'down' if asset_price >= self.price_usd else 'up'

    def turn_off(self) -> None:
        if not self.transaction_id:
            self.status = 'off'

    def turn_on(self) -> None:
        if self.transaction_id and self.status != 'on':
            self.transaction_id = None
            self.asset_id = None
        self.status = 'on'

    def delete(self) -> None:
        if not self.transaction_id:
            db.session.delete(self)

    def convert_order_to_transaction(self):
        self.transaction.convert_order_to_transaction()


class Watchlist:
    def __init__(self):
        self.assets = []

    @classmethod
    def get(cls, market=None, status=None):
        watchlist = Watchlist()

        if market:
            select = (db.select(WatchlistAsset).distinct()
                      .filter_by(user_id=current_user.id)
                      .join(WatchlistAsset.ticker).filter_by(market=market))

            if status:
                select = select.join(WatchlistAsset.alerts).filter_by(status=status)

            watchlist.assets = tuple(db.session.execute(select).scalars())
        else:
            watchlist.assets = current_user.watchlist
        return watchlist

    def get_asset(self, find_by: str | int | None):
        if find_by:
            try:
                return find_by_attr(current_user.watchlist, 'id', int(find_by))
            except ValueError:
                return find_by_attr(current_user.watchlist, 'ticker_id', find_by)

    def create_asset(self, ticker: Ticker) -> WatchlistAsset:
        asset = WatchlistAsset(ticker=ticker, ticker_id=ticker.id)
        return asset
