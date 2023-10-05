from flask_babel import gettext
from flask_login import UserMixin, current_user

from portfolio_tracker.app import db
from portfolio_tracker.general_functions import float_, get_price_list
from portfolio_tracker.jinja_filters import user_currency


class Details:
    def update_details(self):
        self.profit = int(self.cost_now - self.amount_usd)
        if self.profit > 0:
            self.color = 'text-green'
        elif self.profit < 0:
            self.color = 'text-red'

        self.profit_percent = ''
        if self.profit and self.amount_usd:
            self.profit_percent = abs(int(self.profit / self.amount_usd * 100))


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    wallet_asset_id = db.Column(db.Integer, db.ForeignKey('wallet_asset.id'))
    against_ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    price_usd = db.Column(db.Float)
    amount = db.Column(db.Float)
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'))
    order = db.Column(db.Boolean)
    # Relationships
    asset = db.relationship('Asset',
                            backref=db.backref('transactions', lazy=True))
    wallet = db.relationship('Wallet',
                             backref=db.backref('transactions', lazy=True))
    wallet_asset = db.relationship('WalletAsset',
                             backref=db.backref('transactions', lazy=True))
    against_ticker = db.relationship('Ticker')
    # buy_for_wallet_ticker = db.relationship('WalletTicker',
    #                          backref=db.backref('pay_for', lazy=True))

    # id = db.Column(db.Integer, primary_key=True)
    # date = db.Column(db.Date)
    # base_asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    # quote_asset_id = db.Column(db.Integer, db.ForeignKey('wallet_asset.id'))
    # quote_ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    # base_quantity = db.Column(db.Float)
    # quote_quantity = db.Column(db.Float)
    # price = db.Column(db.Float)
    # price_usd = db.Column(db.Float)
    # type = db.Column(db.String(2))
    # comment = db.Column(db.String(1024))
    # # wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'))
    # order = db.Column(db.Boolean)
    # # Relationships
    # asset = db.relationship('Asset',
    #                         backref=db.backref('transactions', lazy=True))
    # # wallet = db.relationship('Wallet',
    # #                          backref=db.backref('transactions', lazy=True))
    # wallet_asset = db.relationship('WalletAsset',
    #                          backref=db.backref('transactions', lazy=True))
    # quote_ticker = db.relationship('Ticker')


    def update_details(self):
        if self.type == '+1':
            self.type_name = gettext('Buy')
            self.color = 'text-green'
        elif self.type == '-1':
            self.type_name = gettext('Sell')
            self.color = 'text-red'


    def update_details_to_wallet(self):
        if self.type == '+1':
            self.type_symbol = '-'
            self.type_name = gettext('Покупка %(name)s',
                                     name=self.asset.ticker.name)
            self.color = 'text-red'
        elif self.type == '-1':
            self.type_symbol = '+'
            self.type_name = gettext('Продажа %(name)s',
                                     name=self.asset.ticker.name)
            self.color = 'text-green'


class Asset(db.Model, Details):
    id = db.Column(db.Integer, primary_key=True)
    ticker_id = db.Column(db.Integer, db.ForeignKey('ticker.id'))
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


    def get_quantity(self):
        quantity = 0
        for transaction in self.transactions:
            if not transaction.order:
                quantity += transaction.quantity
        return quantity


    def update_price(self, price_list):
        self.price = float_(price_list.get(self.ticker_id))
        self.quantity = 0
        self.amount = 0
        self.amount_usd = 0
        self.in_orders = 0
        self.is_empty = self.is_empty()
        self.color = ''

        for transaction in self.transactions:
            transaction.update_details()
            if transaction.order:
                if transaction.type != '-1':
                    self.in_orders -= transaction.amount
                continue

            self.amount -= transaction.amount
            self.amount_usd += transaction.quantity * transaction.price_usd
            self.quantity += transaction.quantity
            
        self.cost_now = self.quantity * self.price


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
        self.amount = 0
        self.cost_now = 0
        self.is_empty = self.is_empty()

        for body in self.bodies:
            self.amount += body.amount
            self.cost_now += body.cost_now

        for transaction in self.transactions:
            transaction.update_details()
            self.cost_now += transaction.amount

        self.profit = int(self.cost_now - self.amount)
        if self.profit > 0:
            self.color = 'text-green'
        elif self.profit < 0:
            self.color = 'text-red'

        self.profit_percent = ''
        if self.profit and self.amount:
            self.profit_percent = abs(int(self.profit / self.amount * 100))

        self.amount = int(self.amount)
        self.cost_now = int(self.cost_now)


class OtherTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32))
    asset_id = db.Column(db.Integer, db.ForeignKey('other_asset.id'))
    amount = db.Column(db.Float)
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
    amount = db.Column(db.Float)
    cost_now = db.Column(db.Float)
    comment = db.Column(db.String(1024))
    # Relationships
    asset = db.relationship('OtherAsset',
                            backref=db.backref('bodies', lazy=True))


class Ticker(db.Model):
    # id = db.Column(db.Integer, primary_key=True)
    id = db.Column(db.String(256), primary_key=True)
    name = db.Column(db.String(1024))
    symbol = db.Column(db.String(124))
    image = db.Column(db.String(1024))
    market_cap_rank = db.Column(db.Integer)
    market = db.Column(db.String(32))
    stable = db.Column(db.Boolean)


# class TickerHistory(db.Model):
#     id = db.Column(db.String(256), primary_key=True)
#     market_id = db.Column(db.String(32), primary_key=True)
#     costs_in_usd = db.Column(db.Float, default=0)
#     date = db.Column(db.Date, primary_key=True)


class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(255))
    comment = db.Column(db.String(1024))
    # Relationships
    user = db.relationship('User',
                           backref=db.backref('wallets', lazy=True))


    def is_empty(self):
        return None
        return not(self.transactions)

    def get_asset(self, id=None, ticker_id=None):
        if id:
            for asset in self.wallet_assets:
                if asset.id == id:
                    return asset
        elif ticker_id:
            for asset in self.wallet_assets:
                if asset.ticker_id == ticker_id:
                    return asset
        return None

    def update_price(self, price_list):
        self.cost_now = 0
        self.in_orders = 0
        self.free = 0
        self.is_empty = self.is_empty()
        self.assets = []
        self.stable_assets = []

        for asset in self.wallet_assets:
            asset.update_price(price_list)

            # Стейблкоины и валюта
            if asset.ticker.stable:
                self.stable_assets.append(asset)
                self.free += asset.free * asset.price
                self.in_orders += asset.in_orders * asset.price

            # Активы
            else:
                self.assets.append(asset)
                self.cost_now += asset.cost_now


    def free_money(self, price_list):
        free = 0
        for asset in self.wallet_assets:

            if not asset.ticker.stable:
                continue

            asset.update_price(price_list)
            free += asset.free * price_list.get(asset.ticker_id, 0)
        return int(free)


    def free_stable(self):
        price_list = get_price_list()
        stable_assets = []

        print(self.name)
        for asset in self.wallet_assets:

            print(asset.ticker_id, asset.ticker.stable)
            if asset.ticker.stable:
                asset.update_price(price_list)
                stable_assets.append(asset)
        return stable_assets


class WalletAsset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'))
    ticker_id = db.Column(db.Integer, db.ForeignKey('ticker.id'))
    # Relationships
    wallet = db.relationship('Wallet',
                           backref=db.backref('wallet_assets', lazy=True))
    ticker = db.relationship('Ticker',
                             backref=db.backref('ticker_wallets', lazy=True))

    def get_quantity(self):
        quantity = 0
        for transaction in self.transactions:
            if not transaction.order:
                quantity += transaction.quantity
        self.quantity = quantity
        return quantity

    def update_price(self, price_list):
        ticker = self.ticker
        self.amount = 0
        self.quantity = 0
        self.in_orders = 0
        self.asset_in_orders = 0
        self.all_transactions = []
        self.price = float_(price_list.get(ticker.id))

        # Транзакции в кошельке
        for transaction in self.wallet_transactions:
            self.all_transactions.append(transaction)
            self.amount += transaction.amount
            self.quantity += float(transaction.amount)
            transaction.update_details()

        # Транзакции в портфелях
        if ticker.stable:
            # Добавляем транзакции с участием стейбла

            for transaction in self.wallet.transactions:
                if transaction.against_ticker_id != self.ticker_id:
                    continue

            # for transaction in self.transactions:

                transaction.update_details_to_wallet()
                self.all_transactions.append(transaction)

                if transaction.order:
                    if transaction.type == '+1':
                        self.in_orders -= transaction.amount
                else:
                    self.amount += transaction.amount

        else:
            self.cost_now = 0

            for transaction in self.transactions:
                self.all_transactions.append(transaction)
                if transaction.order:
                    if transaction.type == '+1':
                        self.in_orders -= transaction.amount
                    else:
                        self.asset_in_orders -= transaction.quantity
                else:
                    self.quantity += transaction.quantity

                transaction.update_details()


        if ticker.stable:
            self.free = self.amount - self.in_orders
        else:
            self.cost_now = self.quantity * self.price


class WalletTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wallet_asset_id = db.Column(db.Integer, db.ForeignKey('wallet_asset.id'))
    related_transaction = db.Column(db.Integer)
    date = db.Column(db.String(32))
    amount = db.Column(db.Float, default=0)
    type = db.Column(db.String(24))
    # Relationships
    wallet_asset = db.relationship('WalletAsset',
                              backref=db.backref('wallet_transactions', lazy=True))


    def update_details(self):
        if self.type == '+1':
            self.type_symbol = '+'
            self.color = 'text-green'
            if self.related_transaction:
                self.type_name = gettext('TransferIn')
            else:
                self.type_name = gettext('Input')
        elif self.type == '-1':
            self.type_symbol = '-'
            self.color = 'text-red'
            if self.related_transaction:
                self.type_name = gettext('TransferOut')
            else:
                self.type_name = gettext('Output')
        self.get_related_transaction()

    # Ищем связанные транзакции
    def get_related_transaction(self):
        if self.related_transaction:
            for wallet in current_user.wallets:
                if wallet.id == self.wallet_asset.wallet_id:
                    continue
                for asset in wallet.wallet_assets:
                    for wallet_transaction in asset.wallet_transactions:
                        if wallet_transaction.id == self.related_transaction:
                            self.related = wallet_transaction
                            return None
        return None




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
        for asset in self.assets:
            if asset.transactions:
                return False
        for asset in self.other_assets:
            if asset.bodies:
                return False
            if asset.transactions:
                return False
        return True


    def update_price(self, price_list):
        # self.amount = 0
        self.cost_now = 0
        self.in_orders = 0
        self.amount_usd = 0
        self.is_empty = self.is_empty()

        for asset in self.assets:
            asset.update_price(price_list)
            asset.update_details()

            # self.amount += asset.amount
            self.amount_usd += asset.amount_usd
            self.cost_now += asset.cost_now
            self.in_orders += asset.in_orders

        for asset in self.other_assets:
            asset.update_details()

            # self.amount += asset.amount
            self.cost_now += asset.cost_now


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
    currency = db.Column(db.String(32), default='')
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
