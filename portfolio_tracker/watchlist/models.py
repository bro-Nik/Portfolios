from __future__ import annotations
from typing import List
from datetime import datetime, timezone

from sqlalchemy.orm import Mapped

from ..app import db


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
        db.session.commit()

    def is_empty(self) -> bool:
        return not (self.alerts or self.comment)

    def delete_if_empty(self) -> None:
        for alert in self.alerts:
            if not alert.transaction_id:
                alert.delete()
        db.session.commit()  # ToDo переделать
        if self.is_empty():
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
        db.session.commit()

        self.price_usd = self.price / self.price_ticker.price
        self.comment = form['comment']

        asset_price = self.watchlist_asset.ticker.price
        self.type = 'down' if asset_price >= self.price_usd else 'up'

        db.session.commit()

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
