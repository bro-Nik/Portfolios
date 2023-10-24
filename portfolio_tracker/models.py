from datetime import datetime
from flask import session
from flask_babel import gettext
from flask_login import UserMixin, current_user

from portfolio_tracker.app import db, app
from portfolio_tracker.general_functions import float_, get_price, get_price_list



class Details:
    def update_details(self):
        self.profit = self.cost_now - self.amount
        self.color = ''

        round_profit = round(self.profit)
        if round_profit > 0:
            self.color = 'text-green'
        elif round_profit < 0:
            self.color = 'text-red'

        self.profit_percent = ''
        if self.profit and self.amount:
            self.profit_percent = abs(int(self.profit / self.amount * 100))


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime)
    ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    ticker2_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    quantity = db.Column(db.Float)
    quantity2 = db.Column(db.Float)
    price = db.Column(db.Float)
    price_usd = db.Column(db.Float)
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'))
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
    order = db.Column(db.Boolean)
    related_transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'))
    # Relationships
    portfolio_asset = db.relationship(
        "Asset",
        primaryjoin="and_(Asset.ticker_id == foreign(Transaction.ticker_id), "
            "Asset.portfolio_id == Transaction.portfolio_id)",
        backref=db.backref('transactions', lazy=True)
    )
    wallet_asset = db.relationship(
        "WalletAsset",
        primaryjoin="and_(or_(WalletAsset.ticker_id == foreign(Transaction.ticker_id), "
            "WalletAsset.ticker_id == foreign(Transaction.ticker2_id)), "
            "WalletAsset.wallet_id == Transaction.wallet_id)",
        viewonly=True,
        backref=db.backref('transactions', lazy=True)
    )
    wallet = db.relationship('Wallet',
                             backref=db.backref('transactions', lazy=True, order_by='Transaction.date.desc()'))
    portfolio = db.relationship('Portfolio',
                             backref=db.backref('transactions', lazy=True))
    base_ticker = db.relationship('Ticker',
                                  foreign_keys=[ticker_id], viewonly=True)
    quote_ticker = db.relationship('Ticker',
                                   foreign_keys=[ticker2_id], viewonly=True)
    related_transaction = db.relationship('Transaction',
                                          foreign_keys=[related_transaction_id],
                                          uselist=False)


    def update_dependencies(self, param=''):
        if param in ('cancel',):
            direction = -1
        else:
            direction = 1

        if self.type in ('Buy', 'Sell'):
            from portfolio_tracker.wallet.wallet import get_wallet_asset
            asset = self.portfolio_asset
            base_asset = get_wallet_asset(self.wallet, self.ticker_id, create=True)
            quote_asset = get_wallet_asset(self.wallet, self.ticker2_id, create=True)
            if base_asset and quote_asset:
                if self.order:
                    if self.type == 'Buy':
                        asset.in_orders += self.quantity * self.price_usd * direction
                        base_asset.buy_orders += self.quantity * self.price_usd * direction
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


    def convert_order_to_transaction(self):
        self.update_dependencies('cancel')
        self.order = 0
        self.date = datetime.now().date()
        if self.alert:
            self.alert.delete()
        self.update_dependencies()


    def delete(self):
        self.update_dependencies('cancel')
        db.session.delete(self)


class Asset(db.Model, Details):
    id = db.Column(db.Integer, primary_key=True)
    ticker_id = db.Column(db.String(256), db.ForeignKey('ticker.id'))
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
    percent = db.Column(db.Float, default=0)
    comment = db.Column(db.String(1024))
    quantity = db.Column(db.Float, default=0)
    in_orders = db.Column(db.Float, default=0)
    amount = db.Column(db.Float, default=0)
    # Relationships
    ticker = db.relationship('Ticker',
                             backref=db.backref('assets', lazy=True))
    portfolio = db.relationship('Portfolio',
                                backref=db.backref('assets', lazy=True))


    def is_empty(self):
        return not(self.transactions)


    # перенести в базу (а может и не надо)
    def get_free(self):
        free = self.quantity
        for transaction in self.transactions:
            if transaction.order and transaction.type == 'Sell':
                free += transaction.quantity
        return free


    def update_price(self):
        price_list = get_price_list()
        self.price = price_list.get(self.ticker_id, 0)
        self.cost_now = self.quantity * self.price


    def delete(self):
        for transaction in self.transactions:
            transaction.delete()

        for alert in self.alerts:
            # отставляем уведомления
            alert.asset_id = None
            alert.comment = gettext('Портфель %(name)s удален',
                                    name=self.portfolio.name)

        db.session.delete(self)


class OtherAsset(db.Model, Details):
    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
    name = db.Column(db.String(255))
    percent = db.Column(db.Float, default=0)
    amount = db.Column(db.Float, default=0)
    cost_now = db.Column(db.Float, default=0)
    comment = db.Column(db.String(1024), default='')
    # Relationships
    portfolio = db.relationship('Portfolio',
                                backref=db.backref('other_assets', lazy=True))

    def is_empty(self):
        return not(self.bodies or self.transactions)


    def delete(self):
        for body in self.bodies:
            body.delete()
        for transaction in self.transactions:
            transaction.delete()
        db.session.delete(self)


class OtherTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime)
    asset_id = db.Column(db.Integer, db.ForeignKey('other_asset.id'))
    amount = db.Column(db.Float)
    amount_with_ticker = db.Column(db.Float)
    amount_ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    # Relationships
    asset = db.relationship('OtherAsset',
                            backref=db.backref('transactions', lazy=True))
    amount_ticker = db.relationship('Ticker', uselist=False)


    def update_dependencies(self, param=''):
        if param in ('cancel', ):
            direction = -1
        else:
            direction = 1

        self.asset.cost_now += self.amount * direction


    def delete(self):
        self.update_dependencies('cancel')
        db.session.delete(self)


class OtherBody(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    date = db.Column(db.DateTime)
    asset_id = db.Column(db.Integer, db.ForeignKey('other_asset.id'))
    amount = db.Column(db.Float)
    amount_with_ticker = db.Column(db.Float)
    amount_ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    cost_now = db.Column(db.Float)
    cost_now_ticker = db.Column(db.Float)
    comment = db.Column(db.String(1024))
    # Relationships
    asset = db.relationship('OtherAsset',
                            backref=db.backref('bodies', lazy=True))
    amount_ticker = db.relationship('Ticker', uselist=False)


    def update_dependencies(self, param=''):
        if param in ('cancel',):
            direction = -1
        else:
            direction = 1

        self.asset.amount += self.amount * direction
        self.asset.cost_now += self.cost_now * direction

    def delete(self):
        self.update_dependencies('cancel')
        db.session.delete(self)


class Ticker(db.Model):
    id = db.Column(db.String(256), primary_key=True)
    name = db.Column(db.String(1024))
    symbol = db.Column(db.String(124))
    image = db.Column(db.String(1024))
    market_cap_rank = db.Column(db.Integer)
    market = db.Column(db.String(32))
    stable = db.Column(db.Boolean)


    def delete(self):
        if self.history:
            for price in self.history:
                db.session.delete(price)
        db.session.delete(self)


class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(255))
    comment = db.Column(db.String(1024))
    # Relationships
    user = db.relationship('User', backref=db.backref('wallets', lazy=True))


    def is_empty(self):
        return not(self.transactions)


    def update_price(self):
        self.cost_now = 0
        self.in_orders = 0
        self.free = 0
        self.assets = []
        self.stable_assets = []

        for asset in self.wallet_assets:
            asset.update_price()

            # Стейблкоины и валюта
            if asset.ticker.stable:
                self.stable_assets.append(asset)
                self.free += asset.free * asset.price
                print(asset.ticker.name, ' ', asset.free * asset.price)
                self.in_orders += asset.buy_orders * asset.price
            # Активы
            else:
                self.assets.append(asset)
            self.cost_now += asset.cost_now


    def delete(self):
        for asset in self.wallet_assets:
            asset.delete()
        db.session.delete(self)


class WalletAsset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'))
    ticker_id = db.Column(db.String(256), db.ForeignKey('ticker.id'))
    quantity = db.Column(db.Float, default=0)
    buy_orders = db.Column(db.Float, default=0)
    sell_orders = db.Column(db.Float, default=0)
    # Relationships
    wallet = db.relationship('Wallet',
                           backref=db.backref('wallet_assets', lazy=True))
    ticker = db.relationship('Ticker',
                             backref=db.backref('ticker_wallets', lazy=True))


    def is_empty(self):
        return not(self.transactions)


    def update_price(self):
        self.price = float_(get_price(self.ticker_id))
        self.cost_now = self.quantity * self.price

        if self.ticker.stable:
            self.free = self.quantity - self.buy_orders
        else:
            self.free = self.quantity - self.sell_orders


    def delete(self):
        for transaction in self.transactions:
            transaction.delete()
        db.session.delete(self)


class Portfolio(db.Model, Details):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    market = db.Column(db.String(32))
    name = db.Column(db.String(255))
    comment = db.Column(db.String(1024))
    percent = db.Column(db.Float, default=0)
    # Relationships
    user = db.relationship('User',
                           backref=db.backref('portfolios', lazy=True))


    def is_empty(self):
        if self.transactions:
            return False
        elif self.assets:
            return False

        for asset in self.other_assets:
            if asset.bodies:
                return False
            if asset.transactions:
                return False
        return True


    def update_price(self):
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


    def delete(self):
        for asset in self.assets:
            asset.delete()
        db.session.delete(self)


class WatchlistAsset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    comment = db.Column(db.Text)
    # Relationships
    user = db.relationship('User',
                           backref=db.backref('watchlist', lazy=True))
    ticker = db.relationship('Ticker', uselist=False)


    def is_empty(self):
        return not(self.alerts and self.comment)


    def update_price(self):
        self.price = float_(get_price(self.ticker_id))


    def delete(self):
        for alert in self.alerts:
            alert.delete()
        db.session.delete(self)


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    watchlist_asset_id = db.Column(db.Integer,
                                    db.ForeignKey('watchlist_asset.id'))
    price = db.Column(db.Float)
    price_usd = db.Column(db.Float)
    price_ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    status = db.Column(db.String(24), default='on')
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'))
    # Relationships
    asset = db.relationship('Asset',
                            backref=db.backref('alerts', lazy=True))
    watchlist_asset = db.relationship('WatchlistAsset',
                                      backref=db.backref('alerts', lazy=True))
    transaction = db.relationship('Transaction',
                                  backref=db.backref('alert', uselist=False))
    price_ticker = db.relationship('Ticker', uselist=False)


    def delete(self):
        db.session.delete(self)


class PriceHistory(db.Model):
    date = db.Column(db.Date, primary_key=True)
    ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'), primary_key=True)
    price_usd = db.Column(db.Float)
    # Relationships
    ticker = db.relationship('Ticker',
                             backref=db.backref('history', lazy=True))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(255))
    locale = db.Column(db.String(32))
    timezone = db.Column(db.String(32))
    currency = db.Column(db.String(32), default='usd')
    currency_ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'),
                                   default=app.config['CURRENCY_PREFIX'] + 'usd')
    # Relationships
    info = db.relationship('userInfo',
                           backref=db.backref('user', lazy=True), uselist=False)
    currency_ticker = db.relationship('Ticker', uselist=False)


class userInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    first_visit = db.Column(db.String(255))
    last_visit = db.Column(db.DateTime, default=datetime.utcnow)
    country = db.Column(db.String(255))
    city = db.Column(db.String(255))
