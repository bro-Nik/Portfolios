from __future__ import annotations
from datetime import datetime, timezone
from typing import List

from flask_babel import gettext
from sqlalchemy.orm import Mapped

from ..app import db
from ..general_functions import from_user_datetime
from ..models import DetailsMixin
from ..wallet.utils import get_wallet_asset
from ..watchlist import utils as watchlist


class Transaction(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    date: datetime = db.Column(db.DateTime)
    ticker_id: str = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    ticker2_id: str = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    quantity: float = db.Column(db.Float)
    quantity2: float = db.Column(db.Float)
    price: float = db.Column(db.Float)
    price_usd: float = db.Column(db.Float)
    type: str = db.Column(db.String(24))
    comment: str = db.Column(db.String(1024))
    wallet_id: int = db.Column(db.Integer, db.ForeignKey('wallet.id'))
    portfolio_id: int = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
    order: bool = db.Column(db.Boolean)
    related_transaction_id: int = db.Column(db.Integer,
                                            db.ForeignKey('transaction.id'))

    # Relationships
    base_ticker: Mapped[Ticker] = db.relationship(
        'Ticker', foreign_keys=[ticker_id], viewonly=True)
    quote_ticker: Mapped[Ticker] = db.relationship(
        'Ticker', foreign_keys=[ticker2_id], viewonly=True)
    related_transaction: Mapped[Transaction] = db.relationship(
        'Transaction', foreign_keys=[related_transaction_id], uselist=False)

    def edit(self, form: dict) -> None:
        self.type = form['type']
        t_type = 1 if self.type in ('Buy', 'Input', 'TransferIn') else -1
        self.date = from_user_datetime(form['date'])
        self.comment = form.get('comment')

        # Portfolio transaction
        if self.type in ('Buy', 'Sell'):
            self.ticker2_id = form['ticker2_id']
            self.price = float(form['price'])
            db.session.commit()
            self.price_usd = self.price * self.quote_ticker.price
            self.wallet_id = form[self.type.lower() + '_wallet_id']
            self.order = bool(form.get('order'))
            if form.get('quantity') is not None:
                self.quantity = float(form['quantity']) * t_type
                self.quantity2 = self.price * self.quantity * -1
            else:
                self.quantity2 = float(form['quantity2']) * t_type * -1
                self.quantity = self.quantity2 / self.price * -1

        # Wallet transaction
        else:
            self.quantity = float(form['quantity']) * t_type

        # Уведомление
        alert = self.alert if self.alert else None
        if not self.order and alert:
            alert.delete()
        elif self.order:
            if not alert:
                watchlist_asset = watchlist.get_watchlist_asset(
                    self.ticker_id, create=True, user=self.portfolio.user)
                alert = watchlist.create_new_alert(watchlist_asset)

            alert.price = self.price
            alert.price_usd = self.price_usd
            alert.price_ticker_id = self.ticker2_id
            alert.date = self.date
            alert.transaction_id = self.id
            alert.asset_id = self.portfolio_asset.id
            alert.comment = self.comment

            alert.type = ('down' if self.base_ticker.price >= alert.price_usd
                          else 'up')
        db.session.commit()

    def update_dependencies(self, param: str = '') -> None:
        if param in ('cancel',):
            direction = -1
        else:
            direction = 1

        if self.type in ('Buy', 'Sell'):
            asset = self.portfolio_asset
            base_asset = get_wallet_asset(self.wallet, self.ticker_id,
                                          create=True)
            quote_asset = get_wallet_asset(self.wallet, self.ticker2_id,
                                           create=True)
            if base_asset and quote_asset:
                if self.order:
                    if self.type == 'Buy':
                        asset.in_orders += (self.quantity
                                            * self.price_usd * direction)
                        base_asset.buy_orders += (self.quantity
                                                  * self.price_usd * direction)
                        quote_asset.buy_orders -= self.quantity2 * direction
                    else:
                        base_asset.sell_orders -= self.quantity * direction

                else:
                    base_asset.quantity += self.quantity * direction
                    quote_asset.quantity += self.quantity2 * direction
                    asset.amount += self.quantity * self.price_usd * direction
                    asset.quantity += self.quantity * direction

        elif self.type in ('Input', 'Output', 'TransferOut', 'TransferIn'):
            self.wallet_asset.quantity += self.quantity * direction

        db.session.commit()

    def convert_order_to_transaction(self) -> None:
        self.update_dependencies('cancel')
        self.order = False
        self.date = datetime.now(timezone.utc)
        if self.alert:
            self.alert.delete()
        self.update_dependencies()

    def delete(self) -> None:
        self.update_dependencies('cancel')
        db.session.delete(self)


class Asset(db.Model, DetailsMixin):
    id = db.Column(db.Integer, primary_key=True)
    ticker_id: str = db.Column(db.String(256), db.ForeignKey('ticker.id'))
    portfolio_id: int = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
    percent: float = db.Column(db.Float, default=0)
    comment: str = db.Column(db.String(1024))
    quantity: float = db.Column(db.Float, default=0)
    in_orders: float = db.Column(db.Float, default=0)
    amount: float = db.Column(db.Float, default=0)

    # Relationships
    ticker: Mapped[Ticker] = db.relationship(
        'Ticker', backref=db.backref('assets', lazy=True))
    transactions: Mapped[List[Transaction]] = db.relationship(
        "Transaction",
        primaryjoin="and_(Asset.ticker_id == foreign(Transaction.ticker_id), "
                    "Asset.portfolio_id == Transaction.portfolio_id)",
        backref=db.backref('portfolio_asset', lazy=True)
    )

    def edit(self, form: dict) -> None:
        comment = form.get('comment')
        percent = form.get('percent')

        if comment is not None:
            self.comment = comment
        if percent is not None:
            self.percent = percent
        db.session.commit()

    def is_empty(self) -> bool:
        return not (self.transactions or self.comment)

    def get_free(self) -> float:
        free = self.quantity
        for transaction in self.transactions:
            if transaction.order and transaction.type == 'Sell':
                free += transaction.quantity
        return free

    def update_price(self) -> None:
        self.price = self.ticker.price
        self.cost_now = self.quantity * self.price

    def delete(self) -> None:
        for transaction in self.transactions:
            transaction.delete()

        for alert in self.alerts:
            # отставляем уведомления
            alert.asset_id = None
            alert.comment = gettext('Портфель %(name)s удален',
                                    name=self.portfolio.name)
        self.alerts = []

        db.session.delete(self)


class OtherAsset(db.Model, DetailsMixin):
    id = db.Column(db.Integer, primary_key=True)
    portfolio_id: int = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
    name: str = db.Column(db.String(255))
    percent: float = db.Column(db.Float, default=0)
    amount: float = db.Column(db.Float, default=0)
    cost_now: float = db.Column(db.Float, default=0)
    comment: str = db.Column(db.String(1024), default='')

    # Relationships
    transactions: Mapped[List[OtherTransaction]] = db.relationship(
        'OtherTransaction', backref=db.backref('asset', lazy=True))
    bodies: Mapped[List[OtherBody]] = db.relationship(
        'OtherBody', backref=db.backref('asset', lazy=True))

    def edit(self, form: dict) -> None:
        name = form.get('name')
        comment = form.get('comment')
        percent = form.get('percent')

        if name is not None:
            if self.name == name:
                n = 2
                while name in [i.name for i in self.portfolio.other_assets]:
                    name = form['name'] + str(n)
                    n += 1

        if name:
            self.name = name
        if comment is not None:
            self.comment = comment
        if percent is not None:
            self.percent = percent or 0
        db.session.commit()

    def is_empty(self) -> bool:
        return not (self.bodies or self.transactions or self.comment)

    def delete(self) -> None:
        for body in self.bodies:
            body.delete()
        for transaction in self.transactions:
            transaction.delete()
        db.session.commit()
        db.session.delete(self)


class OtherTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date: datetime = db.Column(db.DateTime)
    asset_id: int = db.Column(db.Integer, db.ForeignKey('other_asset.id'))
    amount: float = db.Column(db.Float)
    amount_ticker_id: str = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    amount_usd: float = db.Column(db.Float, default=0)
    type: str = db.Column(db.String(24))
    comment: str = db.Column(db.String(1024))

    # Relationships
    amount_ticker: Mapped[Ticker] = db.relationship('Ticker', uselist=False)

    def edit(self, form: dict) -> None:
        self.date = from_user_datetime(form['date'])
        self.comment = form['comment']
        self.type = form['type']
        t_type = 1 if self.type == 'Profit' else -1
        self.amount_ticker_id = form['amount_ticker_id']
        self.amount = float(form['amount']) * t_type
        db.session.commit()

        self.amount_usd = self.amount * self.amount_ticker.price
        db.session.commit()

    def update_dependencies(self, param: str = '') -> None:
        if param in ('cancel', ):
            direction = -1
        else:
            direction = 1

        self.asset.cost_now += self.amount_usd * direction

    def delete(self) -> None:
        self.update_dependencies('cancel')
        db.session.delete(self)


class OtherBody(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(255))
    date: datetime = db.Column(db.DateTime)
    asset_id: int = db.Column(db.Integer, db.ForeignKey('other_asset.id'))
    amount: float = db.Column(db.Float)
    amount_usd: float = db.Column(db.Float, default=0)
    amount_ticker_id: str = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    cost_now: float = db.Column(db.Float, default=0)
    cost_now_usd: float = db.Column(db.Float, default=0)
    cost_now_ticker_id: str = db.Column(db.String(32),
                                        db.ForeignKey('ticker.id'))
    comment: str = db.Column(db.String(1024))

    # Relationships
    amount_ticker: Mapped[Ticker] = db.relationship(
        'Ticker', foreign_keys=[amount_ticker_id], viewonly=True)
    cost_now_ticker: Mapped[Ticker] = db.relationship(
        'Ticker', foreign_keys=[cost_now_ticker_id], viewonly=True)

    def edit(self, form: dict) -> None:
        self.name = form['name']
        self.amount = float(form['amount'])
        self.cost_now = float(form['cost_now'])

        self.amount_ticker_id = form['amount_ticker_id']
        self.cost_now_ticker_id = form['cost_now_ticker_id']

        db.session.commit()
        self.amount_usd = self.amount * self.amount_ticker.price
        self.cost_now_usd = self.cost_now * self.cost_now_ticker.price

        self.comment = form['comment']
        self.date = from_user_datetime(form['date'])

        db.session.commit()

    def update_dependencies(self, param: str = '') -> None:
        if param in ('cancel',):
            direction = -1
        else:
            direction = 1

        self.asset.amount += self.amount_usd * direction
        self.asset.cost_now += self.cost_now_usd * direction

    def delete(self) -> None:
        self.update_dependencies('cancel')
        db.session.delete(self)


class Ticker(db.Model):
    id = db.Column(db.String(256), primary_key=True)
    name: str = db.Column(db.String(1024))
    symbol: str = db.Column(db.String(124))
    image: str = db.Column(db.String(1024))
    market_cap_rank: int | None = db.Column(db.Integer)
    price: float = db.Column(db.Float, default=0)
    market: str = db.Column(db.String(32))
    stable: bool = db.Column(db.Boolean)

    def edit(self, form: dict) -> None:
        self.id = form.get('id')
        self.symbol = form.get('symbol')
        self.name = form.get('name')
        self.stable = bool(form.get('stable'))
        db.session.commit()

    def get_history_price(self, date: datetime.date) -> float | None:
        if date:
            for day in self.history:
                if day.date == date:
                    return day.price_usd

    def set_price(self, date: datetime.date, price: float) -> None:
        d = None
        for day in self.history:
            if day.date == date:
                d = day
                break

        if not d:
            d = PriceHistory(date=date)
            self.history.append(d)
        d.price_usd = price

    def delete(self) -> None:
        if self.history:
            for price in self.history:
                price.ticker_id = None
                db.session.delete(price)
            db.session.commit()
        db.session.delete(self)


class Portfolio(db.Model, DetailsMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey('user.id'))
    market: str = db.Column(db.String(32))
    name: str = db.Column(db.String(255))
    comment: str = db.Column(db.String(1024))
    percent: float = db.Column(db.Float, default=0)

    # Relationships
    assets: Mapped[List[Asset]] = db.relationship(
        'Asset', backref=db.backref('portfolio', lazy=True))
    other_assets: Mapped[List[OtherAsset]] = db.relationship(
        'OtherAsset', backref=db.backref('portfolio', lazy=True))
    transactions: Mapped[List[Transaction]] = db.relationship(
        'Transaction', backref=db.backref('portfolio', lazy=True))

    def edit(self, form: dict) -> None:
        name = form.get('name')
        comment = form.get('comment')
        percent = form.get('percent') or 0

        if name is not None:
            portfolios = self.user.portfolios

            names = [i.name for i in portfolios if i.market == self.market]
            if name in names:
                n = 2
                while str(name) + str(n) in names:
                    n += 1
                name = str(name) + str(n)

        if name:
            self.name = name

        self.percent = percent
        self.comment = comment
        db.session.commit()

    def is_empty(self) -> bool:
        return not (self.assets or self.other_assets or self.comment)

    def update_price(self) -> None:
        self.cost_now = 0
        self.in_orders = 0
        self.amount = 0

        for asset in self.assets:
            asset.update_price()
            asset.update_details()
            self.amount += asset.amount
            self.cost_now += asset.cost_now
            self.in_orders += asset.in_orders

        for asset in self.other_assets:
            asset.update_details()
            self.cost_now += asset.cost_now
            self.amount += asset.amount

    def delete(self) -> None:
        for asset in self.assets:
            asset.delete()
        for asset in self.other_assets:
            asset.delete()
        db.session.commit()
        db.session.delete(self)


class PriceHistory(db.Model):
    date: date = db.Column(db.Date, primary_key=True)
    ticker_id: str = db.Column(db.String(32), db.ForeignKey('ticker.id'),
                               primary_key=True)
    price_usd: float = db.Column(db.Float)

    # Relationships
    ticker: Mapped[Ticker] = db.relationship(
        'Ticker', backref=db.backref('history', lazy=True))
