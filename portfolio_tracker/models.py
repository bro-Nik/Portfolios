from datetime import datetime
from flask import current_app, request, session
from flask_babel import gettext
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
import requests

from portfolio_tracker.app import db
from portfolio_tracker.general_functions import get_price, get_price_list
from portfolio_tracker.user.utils import from_user_datetime
# from portfolio_tracker.watchlist.watchlist import get_watchlist_asset
# from portfolio_tracker.watchlist.watchlist import get_watchlist_asset



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

    def update(self, form):
        alert = self.alert if self.alert else None

        self.type = form['type']
        t_type = 1 if self.type == 'Buy' else -1
        self.date = from_user_datetime(form['date'])
        self.ticker2_id = form['ticker2_id']
        self.price = float(form['price'])
        self.price_usd = self.price * get_price(self.ticker2_id, 1)
        self.comment = form['comment']
        self.wallet_id = form[self.type.lower() + '_wallet_id']
        self.order = bool(form.get('order'))

        if form.get('quantity'):
            self.quantity = float(form['quantity']) * t_type
            self.quantity2 = self.price * self.quantity * -1
            session['transaction_calculation_type'] = 'quantity'
        else:
            self.quantity2 = float(form['quantity2']) * t_type * -1
            self.quantity = self.quantity2 / self.price * -1
            session['transaction_calculation_type'] = 'amount'

        # Уведомление
        if not self.order and alert:
            alert.delete()
        elif self.order:
            if not alert:
                alert = Alert()
                watchlist_asset = get_watchlist_asset(self.ticker_id, True)
                if watchlist_asset:
                    watchlist_asset.alerts.append(alert)

            alert.price = self.price_usd
            alert.price_usd = self.price_usd
            alert.price_ticker_id = self.ticker2_id
            alert.date = self.date
            alert.transaction_id = self.id
            alert.asset_id = self.asset_id
            alert.comment = self.comment

            asset_price = get_price(self.ticker_id, 1)
            alert.type = 'down' if asset_price >= alert.price_usd else 'up'
        db.session.commit()


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

        db.session.commit()


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
        self.price = get_price(self.ticker_id, 0)
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
                           # backref=db.backref('portfolios', lazy='dynamic'))
                           backref=db.backref('portfolios', lazy=True))
    lazy='dynamic'


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
        self.price = get_price(self.ticker_id, 0)


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
    currency = db.Column(db.String(32))
    currency_ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    # currency_ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'),
    #                                default=current_app.config['CURRENCY_PREFIX'] + 'usd')
    # Relationships
    info = db.relationship('UserInfo',
                           backref=db.backref('user', lazy=True), uselist=False)
    currency_ticker = db.relationship('Ticker', uselist=False)


    @staticmethod
    def create_new_user(email, password):
        new_user = User(email=email)
        new_user.set_password(password)
        new_user.create_first_wallet()
        new_user.change_currency()
        new_user.change_locale()

        new_user.info = UserInfo()

        db.session.add(new_user)
        return new_user


    def set_password(self, password):
        self.password = generate_password_hash(password)


    def check_password(self, password):
        return check_password_hash(self.password, password)


    def change_currency(self, currency='usd'):
        self.currency = currency
        self.currency_ticker_id = current_app.config['CURRENCY_PREFIX'] + currency


    def change_locale(self, locale='en'):
        self.locale = locale


    def create_first_wallet(self):
        wallet = Wallet(name=gettext('Кошелек по умолчанию'))
        asset = WalletAsset(ticker_id=current_app.config['CURRENCY_PREFIX'] + 'usd')
        wallet.wallet_assets.append(asset)
        self.wallets.append(wallet)

        
    def new_login(self):
        if not self.info:
            self.info.append(UserInfo())

        ip = request.headers.get('X-Real-IP')
        if ip:
            response = requests.get('http://ip-api.com/json/{}'.format(ip)).json()
            if response.get('status') == 'success':
                self.info.country = response.get('country')
                self.info.city = response.get('city')


    def update_assets(self):
        for wallet in self.wallets:
            for asset in wallet.wallet_assets:
                asset.quantity = 0
                asset.buy_orders = 0
                asset.sell_orders = 0
                for transaction in asset.transactions:
                    if transaction.type not in ('Buy', 'Sell'):
                        transaction.update_dependencies()
        for portfolio in self.portfolios:
            for asset in portfolio.assets:
                asset.quantity = 0
                asset.in_orders = 0
                asset.amount = 0
                for transaction in asset.transactions:
                    transaction.update_dependencies()


    def cleare(self):

        # alerts
        for asset in self.watchlist:
            for alert in asset.alerts:
                db.session.delete(alert)
            db.session.delete(asset)

        # wallets
        for wallet in self.wallets:
            for asset in wallet.wallet_assets:
                db.session.delete(asset)
            db.session.delete(wallet)

        # portfolios, assets, transactions
        for portfolio in self.portfolios:
            for asset in portfolio.assets:
                for transaction in asset.transactions:
                    db.session.delete(transaction)
                db.session.delete(asset)

            for asset in portfolio.other_assets:
                for body in asset.bodies:
                    db.session.delete(body)
                for transaction in asset.transactions:
                    db.session.delete(transaction)
                db.session.delete(asset)
            db.session.delete(portfolio)
        db.session.commit()


    def delete(self):
        self.cleare()
        if self.info:
            db.session.delete(self.info)

        db.session.delete(self)
        db.session.commit()


    def export_data(self):
        result = {}

        # Wallets
        wallets = result['wallets'] = []
        for wallet in self.wallets:
            wallets.append({
                'id': wallet.id,
                'name': wallet.name,
                'comment': wallet.comment or '',
            })


        # Portfolios
        portfolios = result['portfolios'] = []
        for portfolio in self.portfolios:
            portfolios.append({
                'id': portfolio.id,
                'market': portfolio.market,
                'name': portfolio.name,
                'comment': portfolio.comment or '',
                'percent': portfolio.percent or '',
            })


        # Portfolio Assets
        portfolio_assets = result['portfolio_assets'] = []
        for portfolio in self.portfolios:
            for asset in portfolio.assets:
                portfolio_assets.append({
                    'ticker': {'symbol': asset.ticker.symbol,
                               'market': asset.ticker.market},
                    'portfolio_id': asset.portfolio_id,
                    'comment': asset.comment or '',
                    'percent': asset.percent or '',
                })


        # Watchlist Assets
        watchlist_assets = result['watchlist_assets'] = []
        for asset in self.watchlist:
            if asset.comment or asset.alerts:
                watchlist_assets.append({
                    'ticker': {'symbol': asset.ticker.symbol,
                               'market': asset.ticker.market},
                    'comment': asset.comment or '',
                })


        # Transactions
        transactions = result['transactions'] = []
        for wallet in self.wallets:
            for t in wallet.transactions:
                transaction = {
                    'id': t.id,
                    'date': str(t.date),
                    'wallet': {
                        'id': t.wallet.id,
                        'name': t.wallet.name
                    },
                    'base_ticker': {
                        'symbol': t.base_ticker.symbol,
                        'market': t.base_ticker.market,
                        'quantity': '{} {}'.format(t.quantity, t.base_ticker.symbol)
                    },
                    'comment': t.comment or '',
                    'type': t.type
                }

                if t.portfolio:
                    transaction['portfolio'] = {
                        'id': t.portfolio.id,
                        'name': t.portfolio.name
                    }
                    transaction['quote_ticker'] = {
                        'symbol': t.quote_ticker.symbol,
                        'market': t.quote_ticker.market,
                        'quantity': '{} {}'.format(t.quantity, t.base_ticker.symbol)
                    }
                if t.order:
                    transaction['order'] = t.order
                if t.price:
                    transaction['price'] = t.price
                if t.price_usd:
                    transaction['price_usd'] = t.price_usd
                if t.related_transaction_id:
                    transaction['related_transaction_id'] = t.related_transaction_id

                transactions.append(transaction)


        # Alerts
        alerts = result['alerts'] = []
        for asset in self.watchlist:
            for alert in asset.alerts:
                alerts.append({
                    'date': alert.date,
                    'asset_id': alert.asset_id or '',
                    'ticker': {
                        'symbol': alert.watchlist_asset.ticker.symbol,
                        'market': alert.watchlist_asset.ticker.market,
                    },
                    'price': '{} {}'.format(alert.price, alert.price_ticker.symbol),
                    'price_usd': '{} USD'.format(alert.price_usd),
                    'type': alert.type,
                    'comment': alert.comment or '',
                    'transaction_id': alert.transaction_id or '',
                    'status': alert.status
                })

        return result


    def import_data(self, data):
        pass
        prefixes = {
            'crypto': current_app.config['CRYPTO_PREFIX'],
            'stocks': current_app.config['STOCKS_PREFIX'],
            'currency': current_app.config['CURRENCY_PREFIX'],
        }
        # def get_new_wallet_id(old_id):
        #     for wallet in data['wallets']:
        #         if old_id == wallet['id']:
        #             return int(wallet['new_id'])

        # def get_new_transaction_id(old_id):
        #     for wallet in data['wallets']:
        #         for asset in wallet['assets']:
        #             for transaction in asset['transactions']:
        #                 if old_id == transaction['id']:
        #                     return int(transaction['new_id']) 
        #
        #
        # Wallets
        new_wallets_ids = {}
        for wallet in data['wallets']:
            new_wallet = Wallet(name=wallet['name'],
                                comment=wallet.get('comment'))
            self.wallets.append(new_wallet)
            # db.session.commit()

            # new_wallets_ids[wallet['id']] = new_wallet.id
            new_wallets_ids[wallet['id']] = new_wallet


        # Portfolios
        new_portfolios_ids = {}
        for portfolio in data['portfolios']:
            new_portfolio = Portfolio(market=portfolio['market'],
                                      name=portfolio['name'],
                                      comment=portfolio.get('comment'))
            self.portfolios.append(new_portfolio)
            # db.session.commit()
        #
        #     new_portfolios_ids[portfolio['id']] = new_portfolio.id
        #
        #
        #
        # # Portfolio assets
        # for asset in data['portfolio_assets']:
        #     ticker_id = '{}{}'.format(prefixes.get(asset['ticker']['market']),
        #                               asset['ticker']['symbol'])
        #     new_asset = Asset(ticker_id=ticker_id,
        #                       portfolio_id=new_portfolios_ids.get(asset['portfolio_id']),
        #                       percent=asset.get('percent'),
        #                       comment=asset.get('comment'))
        #     # db.session.commit()
        #
        #
        # # Watchlist Assets
        # for asset in data['watchlist_assets']:
        #     ticker_id = '{}{}'.format(prefixes.get(asset['ticker']['market']),
        #                               asset['ticker']['symbol'])
        #
        #     watchlist_asset = get_watchlist_asset(ticker_id, True)
        #     if watchlist_asset:
        #         watchlist_asset.comment = asset.get('comment', '')
        #
        #     
        #
        # wallet_transactions = []
        #
        #     # for asset in wallet['assets']:
        #     #     new_asset = get_wallet_asset(new_wallet, asset['ticker_id'], True)
        #
        # for transaction in data['transactions']:
        #     ticker_id = '{}{}'.format(prefixes.get(transaction['base_ticker']['market']),
        #                               transaction['base_ticker']['symbol'])
        #     new_transaction = Transaction(
        #         date=transaction['date'],
        #         ticker_id=ticker_id,
        #         # ticker2_id=ticker_id,
        #
        #         quantity=transaction['base_ticker']['quantity'].get('quantity', 0),
        #         quantity2=transaction.get('quantity', 0),
        #         quantity2 = db.Column(db.Float)
        #         price = db.Column(db.Float)
        #         price_usd = db.Column(db.Float)
        #         type = db.Column(db.String(24))
        #         comment = db.Column(db.String(1024))
        #         wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'))
        #         portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
        #         order = db.Column(db.Boolean)
        #         related_transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'))
        #         quantity=transaction['amount'],
        #         wallet_id=new_wallet.id,
        #         related_transaction_id=transaction['related_transaction']
        #         )
        #     if new_transaction.related_transaction_id:
        #         new_transaction.type = 'TransferIn' if transaction['type'] == '+1' else 'TransferOut'
        #     else:
        #         new_transaction.type = 'Input' if transaction['type'] == '+1' else 'Output'
        #
        #     new_wallet.transactions.append(new_transaction)
        #     db.session.commit()
        #     transaction['new_id'] = new_transaction.id
        #     wallet_transactions.append(new_transaction)
        #
        # db.session.commit()
        #
        # for transaction in wallet_transactions:
        #     related = get_new_transaction_id(transaction.related_transaction_id)
        #     transaction.related_transaction_id = related
        #
        #
        #
        #     old_prefix_len = len(old_prefixes[new_portfolio.market])
        #     prefix = prefixes[new_portfolio.market]
        #
        #     for asset in portfolio['assets']:
        #         new_asset = Asset(ticker_id=prefix + asset['ticker_id'][old_prefix_len:],
        #                           percent=asset['percent'],
        #                           comment=asset['comment'])
        #         new_portfolio.assets.append(new_asset)
        #         db.session.commit()
        #
        #         for transaction in asset['transactions']:
        #             wallet_id = get_new_wallet_id(transaction['wallet_id'])
        #             wallet = get_wallet(wallet_id)
        #             wallet_asset = get_wallet_asset(wallet, new_asset.ticker_id,
        #                                             create=True)
        #             new_transaction = Transaction(
        #                 date=transaction['date'],
        #                 ticker_id=new_asset.ticker_id,
        #                 ticker2_id='cu-usd',
        #                 quantity=transaction['quantity'],
        #                 quantity2=transaction['amount'],
        #                 price=transaction['price'],
        #                 price_usd=transaction['price'],
        #                 comment=transaction['comment'],
        #                 wallet_id=wallet_id,
        #                 portfolio_id=new_portfolio.id,
        #                 order=transaction['order']
        #                 )
        #             new_transaction.type = 'Buy' if transaction['type'] == '+1' else 'Sell'
        #
        #             new_asset.transactions.append(new_transaction)
        #
        #             if new_transaction.order:
        #                 watchlist_asset = get_watchlist_asset(new_asset.ticker_id, True)
        #                 new_transaction.alert.append(Alert(
        #                     asset_id=new_asset.id,
        #                     date=new_transaction.date,
        #                     watchlist_asset_id=watchlist_asset.id,
        #                     price=new_transaction.price,
        #                     price_usd=new_transaction.price,
        #                     price_ticker_id='cu-usd',
        #                     type='down' if new_transaction.type == '+' else 'up',
        #                     status='on'
        #                 ))
        #
        #         for alert in asset['alerts']:
        #             watchlist_asset = get_watchlist_asset(new_asset.ticker_id, True)
        #             new_alert = Alert(
        #                 date=alert['date'],
        #                 asset_id=new_asset.id,
        #                 watchlist_asset_id=watchlist_asset.id,
        #                 price=alert['price'],
        #                 price_usd=alert['price'],
        #                 price_ticker_id='cu-usd',
        #                 type=alert['type'],
        #                 comment=alert['comment'],
        #                 status=alert['status']
        #                 )
        #             db.session.add(new_alert)
        #
        # db.session.commit()


        # for ticker in data['whitelist_tickers']:
        #     watchlist_asset = get_watchlist_asset(ticker.get('ticker_id'), True)
        #     watchlist_asset.comment = ticker.get('comment', '')
        #     
        #     for alert in ticker.get('alerts'):
        #         new_alert = Alert(
        #             date=alert.get('date'),
        #             watchlist_asset_id=watchlist_asset.id,
        #             price=alert.get('price'),
        #             price_usd=alert.get('price'),
        #             price_ticker_id='cu-usd',
        #             type=alert.get('type'),
        #             comment=alert.get('comment'),
        #             status=alert.get('status')
        #             )
        #         watchlist_asset.alerts.append(new_alert)
        #         
        # db.session.commit()


        # for portfolio in user.portfolios:
        #     for transaction in portfolio.transactions:
        #         transaction.update_dependencies()
        # for wallet in user.wallets:
        #     for transaction in wallet.transactions:
        #         transaction.update_dependencies()
        # db.session.commit()



class UserInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    first_visit = db.Column(db.DateTime, default=datetime.utcnow)
    last_visit = db.Column(db.DateTime, default=datetime.utcnow)
    country = db.Column(db.String(255))
    city = db.Column(db.String(255))
