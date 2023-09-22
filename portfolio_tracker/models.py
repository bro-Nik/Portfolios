from flask_babel import gettext
from flask_login import UserMixin

from portfolio_tracker.app import db
from portfolio_tracker.general_functions import float_


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    total_spent = db.Column(db.Float)
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'))
    order = db.Column(db.Boolean)
    # Relationships
    asset = db.relationship('Asset',
                            backref=db.backref('transactions', lazy=True))
    wallet = db.relationship('Wallet',
                             backref=db.backref('transactions', lazy=True))

    def update_details(self):
        if self.type == '+':
            self.type_name = gettext('Buy')
            self.color = 'text-green'
        elif self.type == '-':
            self.type_name = gettext('Sell')
            self.color = 'text-red'


class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker_id = db.Column(db.String(255), db.ForeignKey('ticker.id'))
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
    percent = db.Column(db.Float, default=0)
    comment = db.Column(db.String(1024))
    # Relationships
    ticker = db.relationship('Ticker',
                             backref=db.backref('assets', lazy=True))
    portfolio = db.relationship('Portfolio',
                                backref=db.backref('assets', lazy=True))


    def is_empty(self):
        return not(self.transactions)


    def update_details(self, price_list):
        self.price = float_(price_list[self.portfolio.market_id].get(self.ticker_id))
        self.quantity = 0
        self.total_spent = 0
        self.in_orders = 0
        self.is_empty = self.is_empty()
        self.color = ''

        for transaction in self.transactions:
            transaction.update_details()
            if transaction.order:
                if transaction.type != '-':
                    self.in_orders += transaction.total_spent
                continue

            self.total_spent += transaction.total_spent
            self.quantity += transaction.quantity
            
        self.cost_now = self.quantity * self.price
        self.profit = int(self.cost_now - self.total_spent)
        if self.profit > 0:
            self.color = 'text-green'
        elif self.profit < 0:
            self.color = 'text-red'

        self.profit_percent = ''
        if self.profit and self.total_spent:
            self.profit_percent = abs(int(self.profit / self.total_spent * 100))

        self.total_spent = int(self.total_spent)
        self.cost_now = int(self.cost_now)
        self.in_orders = int(self.in_orders)


class OtherAsset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
    name = db.Column(db.String(255))
    percent = db.Column(db.Float, default=0)
    comment = db.Column(db.String(1024), default='')
    # Relationships
    portfolio = db.relationship('Portfolio',
                                backref=db.backref('other_assets', lazy=True))


    def is_empty(self):
        return not(self.bodies or self.transactions)


    def update_details(self):
        self.total_spent = 0
        self.cost_now = 0
        self.is_empty = self.is_empty()

        for body in self.bodies:
            self.total_spent += body.total_spent
            self.cost_now += body.cost_now

        for transaction in self.transactions:
            transaction.update_details()
            self.cost_now += transaction.total_spent

        self.profit = int(self.cost_now - self.total_spent)
        if self.profit > 0:
            self.color = 'text-green'
        elif self.profit < 0:
            self.color = 'text-red'

        self.profit_percent = ''
        if self.profit and self.total_spent:
            self.profit_percent = abs(int(self.profit / self.total_spent * 100))

        self.total_spent = int(self.total_spent)
        self.cost_now = int(self.cost_now)


class OtherTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32))
    asset_id = db.Column(db.Integer, db.ForeignKey('other_asset.id'))
    total_spent = db.Column(db.Float)
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    # Relationships
    asset = db.relationship('OtherAsset',
                            backref=db.backref('transactions', lazy=True))


    def update_details(self):
        if self.type == '+':
            self.type_name = gettext('Profit')
            self.color = 'text-green'
        elif self.type == '-':
            self.type_name = gettext('Loss')
            self.color = 'text-red'


class OtherBody(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    date = db.Column(db.String(32))
    asset_id = db.Column(db.Integer, db.ForeignKey('other_asset.id'))
    total_spent = db.Column(db.Float)
    cost_now = db.Column(db.Float)
    comment = db.Column(db.String(1024))
    # Relationships
    asset = db.relationship('OtherAsset',
                            backref=db.backref('bodies', lazy=True))


class Ticker(db.Model):
    id = db.Column(db.String(256), primary_key=True)
    name = db.Column(db.String(1024))
    symbol = db.Column(db.String(124))
    image = db.Column(db.String(1024))
    market_cap_rank = db.Column(db.Integer)
    market_id = db.Column(db.String(32),
                          db.ForeignKey('market.id'),
                          primary_key=True)
    # Relationships
    market = db.relationship('Market',
                             backref=db.backref('tickers', lazy=True))


class Market(db.Model):
    id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(255))


class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(255))
    money_all = db.Column(db.Float, default=0)
    comment = db.Column(db.String(1024))
    # Relationships
    user = db.relationship('User',
                           backref=db.backref('wallets', lazy=True))


    def is_empty(self):
        return not(self.transactions or self.money_all)


    def update_details(self, price_list):
        self.total_spent = self.cost_now = self.in_orders = 0
        self.is_empty = self.is_empty()
        self.tickers = []

        for transaction in self.transactions:
            ticker = transaction.asset.ticker
            if ticker not in self.tickers:
                ticker.quantity = 0
                ticker.total_spent = 0
                ticker.cost_now = 0
                ticker.in_orders = 0
                self.tickers.append(ticker)

            if transaction.order:
                if transaction.type != '-':
                    ticker.in_orders += transaction.total_spent
                    self.in_orders += transaction.total_spent
                continue

            price = float_(price_list[ticker.market_id].get(ticker.id))

            ticker.quantity += transaction.quantity
            ticker.total_spent += transaction.total_spent
            ticker.cost_now += transaction.quantity * price

            self.total_spent += transaction.total_spent
            self.cost_now += transaction.quantity * price

        self.total_spent = int(self.total_spent)
        self.cost_now = int(self.cost_now)
        self.in_orders = int(self.in_orders)
        self.free_money = int(self.money_all - self.total_spent - self.in_orders)

        if self.cost_now > self.total_spent:
            self.color = 'text-green'
        elif self.cost_now < self.total_spent:
            self.color = 'text-red'


class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    market_id = db.Column(db.String(32), db.ForeignKey('market.id'))
    name = db.Column(db.String(255))
    comment = db.Column(db.String(1024))
    percent = db.Column(db.Float, default=0)
    # Relationships
    user = db.relationship('User',
                           backref=db.backref('portfolios', lazy=True))
    market = db.relationship('Market',
                             backref=db.backref('portfolios', lazy=True))


    def is_empty(self):
        for asset in self.assets:
            if asset.transactions:
                return False
        for asset in self.other_assets:
            if asset.bodies:
                return False
            if asset.transactions:
                return False
        return True


    def update_details(self, price_list):
        self.total_spent = self.cost_now = self.in_orders = 0
        self.is_empty = self.is_empty()

        for asset in self.assets:
            asset.update_details(price_list)

            self.total_spent += asset.total_spent
            self.cost_now += asset.cost_now
            self.in_orders += asset.in_orders

        for asset in self.other_assets:
            asset.update_details()

            self.total_spent += asset.total_spent
            self.cost_now += asset.cost_now

        self.profit = int(self.cost_now - self.total_spent)
        if self.profit > 0:
            self.color = 'text-green'
        elif self.profit < 0:
            self.color = 'text-red'

        if self.profit and self.total_spent:
            self.profit_percent = abs(int(self.profit / self.total_spent * 100))

        self.total_spent = int(self.total_spent)
        self.cost_now = int(self.cost_now)
        self.in_orders = int(self.in_orders)


class WhitelistTicker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ticker_id = db.Column(db.Integer, db.ForeignKey('ticker.id'))
    comment = db.Column(db.Text)
    # Relationships
    user = db.relationship('User',
                           backref=db.backref('whitelist_tickers', lazy=True))
    ticker = db.relationship('Ticker',
                             backref=db.backref('whitelist_ticker', lazy=True),
                             uselist=False)


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    whitelist_ticker_id = db.Column(db.Integer,
                                    db.ForeignKey('whitelist_ticker.id'))
    price = db.Column(db.Float)
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    status = db.Column(db.String, default='on')
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'))
    # Relationships
    asset = db.relationship('Asset',
                            backref=db.backref('alerts', lazy=True))
    whitelist_ticker = db.relationship('WhitelistTicker',
                                       backref=db.backref('alerts', lazy=True))
    transaction = db.relationship('Transaction',
                                  backref='alert',
                                  uselist=False)


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    value = db.Column(db.String(32))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(255))
    locale = db.Column(db.String(32), default='')
    timezone = db.Column(db.String(32), default='')
    # Relationships
    info = db.relationship('userInfo',
                           backref=db.backref('user', lazy=True), uselist=False)


class userInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    first_visit = db.Column(db.String(255))
    last_visit = db.Column(db.String(255))
    country = db.Column(db.String(255))
    city = db.Column(db.String(255))
