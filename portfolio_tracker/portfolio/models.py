from __future__ import annotations
from datetime import datetime, timezone
import os
from typing import List
from flask import abort, current_app, flash

from flask_babel import gettext
from flask_login import current_user
from sqlalchemy.orm import Mapped

from ..app import db
from ..general_functions import find_by_attr, from_user_datetime, remove_prefix
from ..models import DetailsMixin, TransactionsMixin
from ..wallet.models import Wallet


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
        # Отменить, если есть прошлые изменения
        self.update_dependencies('cancel')

        # Направление сделки (direction)
        self.type = form['type']
        d = 1 if self.type in ('Buy', 'Input', 'TransferIn') else -1

        self.date = from_user_datetime(form['date'])
        self.comment = form.get('comment')

        # Portfolio transaction
        if self.type in ('Buy', 'Sell'):
            self.ticker2_id = form['ticker2_id']
            self.price = float(form['price'])

            quote_ticker = Ticker.get(self.ticker2_id)
            if not quote_ticker:
                return

            self.price_usd = self.price * quote_ticker.price
            self.wallet_id = form[self.type.lower() + '_wallet_id']
            self.order = bool(form.get('order'))
            if form.get('quantity') is not None:
                self.quantity = float(form['quantity']) * d
                self.quantity2 = self.price * self.quantity * -1
            else:
                self.quantity2 = float(form['quantity2']) * d * -1
                self.quantity = self.quantity2 / self.price * -1

        # Wallet transaction
        else:
            self.quantity = float(form['quantity']) * d

        # Уведомление
        alert = self.alert
        if not self.order and alert:
            alert.delete()
        elif self.order:
            if not alert:
                from ..watchlist.models import Watchlist

                watchlist = Watchlist()
                watchlist_asset = watchlist.get_asset(self.ticker_id)
                if not watchlist_asset:
                    watchlist_asset = watchlist.create_asset(self.base_ticker)
                    current_user.watchlist.append(watchlist_asset)
                alert = watchlist_asset.create_alert()
                watchlist_asset.alerts.append(alert)

            alert.price = self.price
            alert.price_usd = self.price_usd
            alert.price_ticker_id = self.ticker2_id
            alert.date = self.date
            alert.transaction_id = self.id
            alert.asset_id = self.portfolio_asset.id
            alert.comment = self.comment

            alert.type = ('down' if self.base_ticker.price >= alert.price_usd
                          else 'up')

    def update_dependencies(self, param: str = '') -> None:
        # Направление сделки (direction)
        d = -1 if param == 'cancel' else 1

        # Кошелек
        wallet = Wallet.get(self.wallet_id)
        if not wallet:
            return

        # Базовый актив кошелька
        w_asset1 = wallet.get_asset(self.ticker_id)
        if not w_asset1:
            ticker1 = Ticker.get(self.ticker_id) or abort(404)
            w_asset1 = wallet.create_asset(ticker1)
            wallet.wallet_assets.append(w_asset1)

        if self.type in ('Buy', 'Sell'):
            # Актив портфеля
            p_asset = self.portfolio_asset or abort(404)

            # Котируемый актив кошелька
            w_asset2 = wallet.get_asset(self.ticker2_id)
            if not w_asset2:
                ticker2 = Ticker.get(self.ticker2_id) or abort(404)
                w_asset2 = wallet.create_asset(ticker2)
                wallet.wallet_assets.append(w_asset2)

            if self.order:
                if self.type == 'Buy':
                    p_asset.in_orders += self.quantity * self.price_usd * d
                    w_asset1.buy_orders += self.quantity * self.price_usd * d
                    w_asset2.buy_orders -= self.quantity2 * d
                elif self.type == 'Sell':
                    w_asset1.sell_orders -= self.quantity * d

            else:
                p_asset.amount += self.quantity * self.price_usd * d
                p_asset.quantity += self.quantity * d
                w_asset1.quantity += self.quantity * d
                w_asset2.quantity += self.quantity2 * d

        elif self.type in ('Input', 'Output', 'TransferOut', 'TransferIn'):
            w_asset1.quantity += self.quantity * d

    def convert_order_to_transaction(self) -> None:
        self.update_dependencies('cancel')
        self.order = False
        self.date = datetime.now(timezone.utc)
        if self.alert:
            self.alert.transaction_id = None
            self.alert.delete()
        self.update_dependencies()

    def delete(self) -> None:
        self.update_dependencies('cancel')
        db.session.delete(self)


class Asset(db.Model, DetailsMixin, TransactionsMixin):
    id = db.Column(db.Integer, primary_key=True)
    ticker_id: str = db.Column(db.String(256), db.ForeignKey('ticker.id'))
    portfolio_id: int = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
    percent: float = db.Column(db.Float, default=0)
    comment: str = db.Column(db.String(1024))
    quantity: float = db.Column(db.Float, default=0)
    in_orders: float = db.Column(db.Float, default=0)
    amount: float = db.Column(db.Float, default=0)
    # average_buy_price: float = db.Column(db.Float, default=0)  # usd

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
        if not self.ticker_id:
            market = form.get('ticker_id')
            if market in ('crypto', 'stocks', 'other'):
                self.market = market
            else:
                return
        comment = form.get('comment')
        percent = form.get('percent')

        if comment is not None:
            self.comment = comment
        if percent is not None:
            self.percent = percent

    def is_empty(self) -> bool:
        return not (self.transactions or self.comment)

    def get_free(self) -> float:
        free = self.quantity
        for transaction in self.transactions:
            if transaction.order and transaction.type == 'Sell':
                free += transaction.quantity
        return free

    @property
    def price(self) -> float:
        return self.ticker.price

    @property
    def average_buy_price(self) -> float:
        return self.amount / self.quantity if self.quantity and self.amount > 0 else 0

    @property
    def cost_now(self) -> float:
        return self.quantity * self.price

    @property
    def profit_percent(self):
        if self.quantity and self.average_buy_price:
            return round(self.profit / (self.average_buy_price * self.quantity) * 100)

    def create_transaction(self) -> Transaction | OtherTransaction:
        """Возвращает новую транзакцию."""
        transaction = Transaction(
            type='Buy',
            ticker_id=self.ticker_id,
            quantity=0,
            portfolio_id=self.portfolio_id,
            date=datetime.now(timezone.utc),
            price=self.price)

        return transaction

    def delete_if_empty(self) -> None:
        if self.is_empty():
            self.delete()
        else:
            flash(gettext('В активе %(name)s есть транзакции',
                          name=self.ticker.name), 'danger')

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


class OtherAsset(db.Model, DetailsMixin, TransactionsMixin):
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

    def is_empty(self) -> bool:
        return not (self.bodies or self.transactions or self.comment)

    def create_transaction(self):
        transaction = OtherTransaction(type='Profit',
                                       amount=0,
                                       date=datetime.now(timezone.utc))
        if self.transactions:
            transaction.amount_ticker = self.transactions[-1].amount_ticker
        else:
            transaction.amount_ticker = current_user.currency_ticker

        return transaction

    def get_body(self, body_id: str | int | None):
        return find_by_attr(self.bodies, 'id', body_id)

    def create_body(self) -> OtherBody:
        """Возвращает новое тело актива."""
        body = OtherBody()
        body.date = datetime.now(timezone.utc)
        if self.bodies:
            body.amount_ticker = self.bodies[-1].amount_ticker
            body.cost_now_ticker = self.bodies[-1].cost_now_ticker
        else:
            body.amount_ticker = current_user.currency_ticker
            body.cost_now_ticker = current_user.currency_ticker

        return body

    def delete_if_empty(self) -> None:
        if self.is_empty():
            self.delete()
        else:
            flash(gettext('Актив %(name)s не пустой',
                          name=self.name), 'danger')

    def delete(self) -> None:
        for body in self.bodies:
            body.delete()
        for transaction in self.transactions:
            transaction.delete()
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

        amount_ticker = Ticker.get(self.amount_ticker_id)
        if amount_ticker:
            self.amount_usd = self.amount * self.amount_ticker.price

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
        self.date = from_user_datetime(form['date'])
        self.comment = form['comment']
        self.amount = float(form['amount'])
        self.cost_now = float(form['cost_now'])

        self.amount_ticker_id = form['amount_ticker_id']
        self.cost_now_ticker_id = form['cost_now_ticker_id']

        amount_ticker = Ticker.get(self.amount_ticker_id)
        cost_now_ticker = Ticker.get(self.cost_now_ticker_id)
        if amount_ticker and cost_now_ticker:
            self.amount_usd = self.amount * amount_ticker.price
            self.cost_now_usd = self.cost_now * cost_now_ticker.price

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
    id: str = db.Column(db.String(256), primary_key=True)
    name: str = db.Column(db.String(1024))
    symbol: str = db.Column(db.String(124))
    image: str | None = db.Column(db.String(1024))
    market_cap_rank: int | None = db.Column(db.Integer)
    price: float = db.Column(db.Float, default=0)
    market: str = db.Column(db.String(32))
    stable: bool = db.Column(db.Boolean)

    def edit(self, form: dict) -> None:
        self.id = form.get('id')
        self.symbol = form.get('symbol')
        self.name = form.get('name')
        self.stable = bool(form.get('stable'))

    @classmethod
    def get(cls, ticker_id: str | None) -> Ticker | None:
        if ticker_id:
            return db.session.execute(
                db.select(Ticker).filter_by(id=ticker_id)).scalar()

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

    def external_url(self):
        external_id = remove_prefix(self.id, self.market)
        if self.market == 'crypto':
            url = 'https://www.coingecko.com/ru/%D0%9A%D1%80%D0%B8%D0%BF%D1%82%D0%BE%D0%B2%D0%B0%D0%BB%D1%8E%D1%82%D1%8B/'
            return f'{url}{external_id}'

    def delete(self) -> None:
        # Цены
        if self.history:
            for price in self.history:
                price.ticker_id = None
                db.session.delete(price)
        # Активы
        if self.assets:
            for asset in self.assets:
                asset.delete()

        # Иконки
        # Папка хранения изображений
        if self.image:
            upload_folder = current_app.config['UPLOAD_FOLDER']
            path = f'{upload_folder}/images/tickers/{self.market}'
            os.remove(f'{path}/24/{self.image}')
            os.remove(f'{path}/40/{self.image}')

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

    @classmethod
    def get(cls, portfolio_id: int | str | None,
            user: User = current_user) -> Portfolio | None:
        return find_by_attr(user.portfolios, 'id', portfolio_id)

    @classmethod
    def create(cls, user: User = current_user) -> Portfolio:
        """Возвращает новый портфель"""
        portfolio = Portfolio()
        return portfolio

    def edit(self, form: dict) -> None:
        if not self.market:
            market = form.get('market')
            if market in ('crypto', 'stocks', 'other'):
                self.market = market
            else:
                return

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

    def is_empty(self) -> bool:
        return not (self.assets or self.other_assets or self.comment)

    def update_price(self) -> None:
        self.cost_now = 0
        self.in_orders = 0
        self.amount = 0

        for asset in self.assets:
            self.cost_now += asset.cost_now
            self.in_orders += asset.in_orders
            self.amount += asset.amount

        for asset in self.other_assets:
            self.cost_now += asset.cost_now
            self.amount += asset.amount if asset.amount > 0 else 0

    @property
    def profit(self):
        profit = 0
        for asset in self.assets:
            profit += asset.profit
        return profit

    @property
    def profit_percent(self):
        spent = 0
        for asset in self.assets:
            if asset.quantity and asset.average_buy_price:
                spent += asset.average_buy_price * asset.quantity

        return round(self.profit / spent * 100) if spent else 0

    def get_asset(self, find_by: str | int | None):
        if find_by:
            if getattr(self, 'market') == 'other':
                return find_by_attr(self.other_assets, 'id', find_by)
            try:
                return find_by_attr(self.assets, 'id', int(find_by))
            except ValueError:
                return find_by_attr(self.assets, 'ticker_id', find_by)

    def create_asset(self, ticker: Ticker) -> Asset:
        """Возвращает новый актив"""
        asset = Asset(ticker=ticker, ticker_id=ticker.id)
        return asset

    def create_other_asset(self) -> OtherAsset:
        """Возвращает новый актив"""
        asset = OtherAsset()
        return asset

    def delete_if_empty(self) -> None:
        if self.is_empty():
            self.delete()
        else:
            flash(gettext('В портфеле %(name)s есть транзакции',
                          name=self.name), 'danger')

    def delete(self) -> None:
        for asset in self.assets:
            asset.delete()
        for asset in self.other_assets:
            asset.delete()
        db.session.delete(self)


class PriceHistory(db.Model):
    date: date = db.Column(db.Date, primary_key=True)
    ticker_id: str = db.Column(db.String(32), db.ForeignKey('ticker.id'),
                               primary_key=True)
    price_usd: float = db.Column(db.Float)

    # Relationships
    ticker: Mapped[Ticker] = db.relationship(
        'Ticker', backref=db.backref('history', lazy=True))
