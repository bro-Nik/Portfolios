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
from ..models import AssetMixin, DetailsMixin, TransactionsMixin
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
    order: bool = db.Column(db.Boolean, default=False)
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
        d = 1 if self.type in ('Buy', 'Input', 'TransferIn', 'Earning') else -1
        print(self.type)

        self.date = from_user_datetime(form['date'])
        self.comment = form.get('comment')


        if self.type in ('Buy', 'Input', 'Earning'):
            self.wallet_id = form['buy_wallet_id']
        elif self.type in ('Sell', 'Output'):
            self.wallet_id = form['sell_wallet_id']

        # Portfolio transaction
        if self.type in ('Buy', 'Sell'):
            # self.ticker2_id = form['ticker2_id']
            self.ticker2_id = form[self.type.lower() + '_ticker2_id']
            self.price = float(form['price'])

            quote_ticker = Ticker.get(self.ticker2_id)
            if not quote_ticker:
                return

            self.price_usd = self.price * quote_ticker.price
            # self.wallet_id = form[self.type.lower() + '_wallet_id']
            self.order = bool(form.get('order'))
            if form.get('quantity') is not None:
                self.quantity = float(form['quantity']) * d
                self.quantity2 = self.price * self.quantity * -1
            else:
                self.quantity2 = float(form['quantity2']) * d * -1
                self.quantity = self.quantity2 / self.price * -1

        # Wallet transaction
        elif self.type in ('Input', 'Output'):
            self.quantity = float(form['quantity']) * d

        elif self.type in ('TransferIn', 'TransferOut'):
            self.quantity = float(form['quantity']) * d
            self.wallet2_id = form.get('buy_wallet_id')
            self.portfolio2_id = form.get('portfolio_id')

        elif self.type in ('Earning'):
            self.quantity = float(form['quantity']) * d

        # Уведомление
        alert = self.alert
        if not self.order and alert:
            alert.transaction_id = None
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

        wallet = Wallet.get(self.wallet_id)
        portfolio = Portfolio.get(self.portfolio_id)
        p_asset1 = p_asset2 = w_asset1 = w_asset2 = None

        # Базовый актив портфеля
        p_asset1 = get_or_create_asset(portfolio, self.ticker_id)
        # Котируемый актив портфеля
        p_asset2 = get_or_create_asset(portfolio, self.ticker2_id)
        # Базовый актив кошелька
        w_asset1 = get_or_create_asset(wallet, self.ticker_id)
        # Котируемый актив кошелька
        w_asset2 = get_or_create_asset(wallet, self.ticker2_id)


        if self.type in ('Buy', 'Sell'):
            # Условия
            if not (p_asset1 and p_asset2 and w_asset1 and w_asset2):
                return

            # Ордер
            if self.order:
                if self.type == 'Buy':
                    p_asset1.buy_orders += self.quantity * self.price_usd * d
                    p_asset2.sell_orders -= self.quantity2 * d
                    w_asset1.buy_orders += self.quantity * self.price_usd * d
                    w_asset2.sell_orders -= self.quantity2 * d
                elif self.type == 'Sell':
                    w_asset1.sell_orders -= self.quantity * d
                    p_asset1.sell_orders -= self.quantity * d

            # Не ордер
            else:
                p_asset1.amount += self.quantity * self.price_usd * d
                p_asset1.quantity += self.quantity * d
                p_asset2.amount += self.quantity2 * p_asset2.price * d
                p_asset2.quantity += self.quantity2 * d

                w_asset1.quantity += self.quantity * d
                w_asset2.quantity += self.quantity2 * d

        elif self.type in ('Earning'):
            # Условия
            if not (p_asset1 and w_asset1):
                return

            p_asset1.quantity += self.quantity * d
            w_asset1.quantity += self.quantity * d

        # elif self.type in ('Input', 'Output') and wallet and portfolio:
        else:
            if portfolio and p_asset1:
                p_asset1.amount += self.quantity * d
                p_asset1.quantity += self.quantity * d
            if wallet and w_asset1:
                w_asset1.quantity += self.quantity * d



    def update_related_transaction(self, asset_parent):
        # Связанная транзакция
        asset2 = get_or_create_asset(asset_parent, self.ticker_id)

        if asset2:
            transaction2 = self.related_transaction
            if not transaction2:
                transaction2 = asset2.create_transaction()
                asset2.transactions.append(transaction2)
                db.session.add(transaction2)

            transaction2.edit({
                'type': ('TransferOut' if self.type == 'TransferIn'
                            else 'TransferIn'),
                'date': self.date,
                'quantity': self.quantity * -1
            })

            transaction2.update_dependencies()

            db.session.flush()
            self.related_transaction_id = transaction2.id
            transaction2.related_transaction_id = self.id


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


def get_or_create_asset(parent, ticker_id):
    if not parent or not ticker_id:
        return

    asset = parent.get_asset(ticker_id)
    if not asset:
        ticker = Ticker.get(ticker_id)
        asset = parent.create_asset(ticker)
    return asset


class Asset(db.Model, DetailsMixin, AssetMixin, TransactionsMixin):
    id = db.Column(db.Integer, primary_key=True)
    ticker_id: str = db.Column(db.String(256), db.ForeignKey('ticker.id'))
    portfolio_id: int = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
    quantity: float = db.Column(db.Float, default=0)
    buy_orders: float = db.Column(db.Float, default=0)
    sell_orders: float = db.Column(db.Float, default=0)
    amount: float = db.Column(db.Float, default=0)
    percent: float = db.Column(db.Float, default=0)
    comment: str = db.Column(db.String(1024))

    # Relationships
    ticker: Mapped[Ticker] = db.relationship(
        'Ticker', backref=db.backref('assets', lazy=True))
    transactions: Mapped[List[Transaction]] = db.relationship(
        "Transaction",
        # primaryjoin="and_(Asset.ticker_id == foreign(Transaction.ticker_id), "
        #             "Asset.portfolio_id == Transaction.portfolio_id)",
        primaryjoin="and_(or_(Asset.ticker_id == foreign(Transaction.ticker_id), Asset.ticker_id == foreign(Transaction.ticker2_id)), "
                    "Asset.portfolio_id == Transaction.portfolio_id)",
        backref=db.backref('portfolio_asset', lazy=True)
    )

    @property
    def average_buy_price(self) -> float:
        return self.amount / self.quantity if self.quantity and self.amount > 0 else 0


    def edit(self, form: dict) -> None:
        comment = form.get('comment')
        percent = form.get('percent')

        if comment is not None:
            self.comment = comment
        if percent is not None:
            self.percent = percent

    def create_transaction(self) -> Transaction | OtherTransaction:
        """Возвращает новую транзакцию."""
        transaction = Transaction(
            type='Buy',
            ticker_id=self.ticker_id,
            quantity=0,
            portfolio_id=self.portfolio_id,
            date=datetime.now(timezone.utc),
            price=0)

        return transaction

    def set_default_data(self):
        self.amount = 0
        self.quantity = 0
        self.sell_orders = 0
        self.buy_orders = 0

    def recalculate(self):
        self.set_default_data()

        # for t in self.transactions:
        #     is_base_asset = bool(self.ticker_id == t.ticker_id)
        #     if is_base_asset:
        #         t.update_dependencies()
            # if t.type in ('Buy', 'Sell'):
            #     if t.order:
            #         if t.type == 'Buy':
            #             self.in_orders += t.quantity * t.price_usd
            #     else:
            #         self.amount += t.quantity * t.price_usd
            #         self.quantity += t.quantity

        # Рабочий
        for t in self.transactions:

            if t.type in ('Buy', 'Sell'):
                if self.ticker_id == t.ticker2_id:
                    # Это котируемый актив
                    if t.order:
                        if t.type == 'Buy':
                            self.sell_orders -= t.quantity2
                        elif t.type == 'Sell':
                            self.buy_orders -= t.quantity2

                    else:
                        self.amount += t.quantity2
                        self.quantity += t.quantity2

                else:
                    # Это базовый актив
                    if t.order:
                        if t.type == 'Sell':
                            self.sell_orders -= t.quantity
                        elif t.type == 'Buy':
                            self.buy_orders -= t.quantity
                        #     w_asset1.sell_orders -= self.quantity * d

                    else:
                        self.amount += t.quantity * t.price_usd
                        self.quantity += t.quantity

            elif t.type in ('Earning'):
                self.quantity += t.quantity

            elif t.type in ('Input', 'Output'):
                self.amount += t.quantity
                self.quantity += t.quantity


    def delete(self) -> None:
        for transaction in self.transactions:
            transaction.delete()

        for alert in self.alerts:
            # отставляем уведомления
            alert.asset_id = None
            alert.comment = gettext('Актив удален из портфеля %(name)s',
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

    @property
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
        if self.is_empty:
            self.delete()
        else:
            flash(gettext('Актив %(name)s не пустой',
                          name=self.name), 'warning')

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
            try:
                os.remove(f'{path}/24/{self.image}')
                os.remove(f'{path}/40/{self.image}')
            except:
                pass

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

    @property
    def is_empty(self) -> bool:
        return not (self.assets or self.other_assets or self.comment)

    def update_info(self) -> None:
        self.cost_now = 0
        self.amount = 0
        self.buy_orders = 0
        self.invested = 0

        prefix = 'other_' if self.market == 'other' else ''
        for asset in getattr(self, f'{prefix}assets'):
            self.cost_now += asset.cost_now
            self.amount += asset.amount
            self.invested += asset.amount if asset.amount > 0 else 0
            if self.market != 'other':
                self.buy_orders += asset.buy_orders

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
        asset = Asset(ticker=ticker,
                      ticker_id=ticker.id)
        asset.set_default_data()
        self.assets.append(asset)
        return asset

    def create_other_asset(self) -> OtherAsset:
        """Возвращает новый актив"""
        asset = OtherAsset()
        return asset

    def delete_if_empty(self) -> None:
        if self.is_empty:
            self.delete()
        else:
            flash(gettext('В портфеле %(name)s есть транзакции',
                          name=self.name), 'warning')

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
