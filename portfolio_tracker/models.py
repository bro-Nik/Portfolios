from datetime import datetime
from flask import current_app, request
from flask_babel import gettext
from flask_login import UserMixin
import requests

from portfolio_tracker.app import db
from portfolio_tracker.general_functions import get_price, from_user_datetime


class DetailsMixin:
    def update_details(self):
        if not hasattr(self, 'cost_now'):
            self.cost_now = 0
        if not hasattr(self, 'amount'):
            self.amount = 0

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
                             backref=db.backref('transactions', lazy=True,
                                                order_by='Transaction.date.desc()'))
    portfolio = db.relationship('Portfolio',
                                backref=db.backref('transactions', lazy=True))
    base_ticker = db.relationship('Ticker',
                                  foreign_keys=[ticker_id], viewonly=True)
    quote_ticker = db.relationship('Ticker',
                                   foreign_keys=[ticker2_id], viewonly=True)
    related_transaction = db.relationship('Transaction',
                                          foreign_keys=[related_transaction_id],
                                          uselist=False)

    def edit(self, form):
        self.type = form['type']
        t_type = 1 if self.type in ('Buy', 'Input', 'TransferIn') else -1
        self.date = from_user_datetime(form['date'])
        self.comment = form.get('comment')

        # Portfolio transaction
        if self.type in ('Buy', 'Sell'):
            self.ticker2_id = form['ticker2_id']
            self.price = float(form['price'])
            self.price_usd = self.price * get_price(self.ticker2_id, 1)
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
                from portfolio_tracker.watchlist.utils import get_watchlist_asset
                watchlist_asset = get_watchlist_asset(self.ticker_id, True, self.portfolio.user)

                alert = Alert()
                if watchlist_asset:
                    watchlist_asset.alerts.append(alert)

            alert.price = self.price_usd
            alert.price_usd = self.price_usd
            alert.price_ticker_id = self.ticker2_id
            alert.date = self.date
            alert.transaction_id = self.id
            alert.asset_id = self.portfolio_asset.id
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
            from portfolio_tracker.wallet.utils import get_wallet_asset
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


class Asset(db.Model, DetailsMixin):
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

    def edit(self, form):
        comment = form.get('comment')
        percent = form.get('percent')

        if comment is not None:
            self.comment = comment
        if percent is not None:
            self.percent = percent
        db.session.commit()

    def is_empty(self):
        return not (self.transactions or self.comment)

    def get_free(self):
        free = self.quantity
        for transaction in self.transactions:
            if transaction.order and transaction.type == 'Sell':
                free += transaction.quantity
        return free

    def update_price(self):
        self.price = get_price(self.ticker_id, 0)
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


class OtherAsset(db.Model, DetailsMixin):
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

    def edit(self, portfolio, form):
        name = form.get('name')
        comment = form.get('comment')
        percent = form.get('percent')

        if name is not None:
            if self.name != name:
                n = 2
                while name in [i.name for i in portfolio.other_assets]:
                    name = request.form['name'] + str(n)
                    n += 1

        if name:
            self.name = name
        if comment is not None:
            self.comment = comment
        if percent is not None:
            self.percent = percent or 0
        db.session.commit()

    def is_empty(self):
        return not (self.bodies or self.transactions)

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
    amount_ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    amount_usd = db.Column(db.Float)
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    # Relationships
    asset = db.relationship('OtherAsset',
                            backref=db.backref('transactions', lazy=True))
    amount_ticker = db.relationship('Ticker', uselist=False)

    def edit(self, form):
        self.type = form['type']
        t_type = 1 if self.type == 'Profit' else -1
        self.amount_ticker_id = form['amount_ticker_id']
        self.amount = float(form['amount']) * t_type
        self.amount_usd = self.amount * get_price(self.amount_ticker_id)
        self.comment = form['comment']
        self.date = from_user_datetime(form['date'])

        db.session.commit()

    def update_dependencies(self, param=''):
        if param in ('cancel', ):
            direction = -1
        else:
            direction = 1

        self.asset.cost_now += self.amount_usd * direction

    def delete(self):
        self.update_dependencies('cancel')
        db.session.delete(self)


class OtherBody(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    date = db.Column(db.DateTime)
    asset_id = db.Column(db.Integer, db.ForeignKey('other_asset.id'))
    amount = db.Column(db.Float)
    amount_usd = db.Column(db.Float)
    amount_ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    cost_now = db.Column(db.Float)
    cost_now_usd = db.Column(db.Float)
    cost_now_ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    comment = db.Column(db.String(1024))
    # Relationships
    asset = db.relationship('OtherAsset',
                            backref=db.backref('bodies', lazy=True))
    amount_ticker = db.relationship('Ticker',
                                    foreign_keys=[amount_ticker_id],
                                    viewonly=True)
    cost_now_ticker = db.relationship('Ticker',
                                      foreign_keys=[cost_now_ticker_id],
                                      viewonly=True)

    def update_dependencies(self, param=''):
        if param in ('cancel',):
            direction = -1
        else:
            direction = 1

        self.asset.amount += self.amount_usd * direction
        self.asset.cost_now += self.cost_now_usd * direction

    def edit(self, form):
        self.name = form['name']
        self.amount_ticker_id = form['amount_ticker_id']
        self.amount = float(form['amount'])
        self.amount_usd = self.amount * get_price(self.amount_ticker_id, 1)
        self.cost_now_ticker_id = form['cost_now_ticker_id']
        self.cost_now = float(form['cost_now'])
        self.cost_now_usd = self.cost_now * get_price(self.cost_now_ticker_id, 1)
        self.comment = form['comment']
        self.date = from_user_datetime(form['date'])

        db.session.commit()

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

    def edit(self, form):
        self.id = form.get('id')
        self.symbol = form.get('symbol')
        self.name = form.get('name')
        self.stable = bool(form.get('stable'))
        db.session.commit()

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

    def edit(self, form):
        name = form.get('name')
        comment = form.get('comment')

        if name is not None:
            user_wallets = self.user.wallets
            names = [i.name for i in user_wallets]
            if name in names:
                n = 2
                while str(name) + str(n) in names:
                    n += 1
                name = str(name) + str(n)

        if name:
            self.name = name

        self.comment = comment
        db.session.commit()

    def is_empty(self):
        return not (self.transactions or self.comment)

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
        return not (self.transactions)

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


class Portfolio(db.Model, DetailsMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    market = db.Column(db.String(32))
    name = db.Column(db.String(255))
    comment = db.Column(db.String(1024))
    percent = db.Column(db.Float, default=0)
    # Relationships
    user = db.relationship('User',
                           backref=db.backref('portfolios', lazy=True))

    def edit(self, form):
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

    def is_empty(self):
        return not (self.assets or self.other_assets or self.comment)

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

    def edit(self, form):
        comment = form.get('comment')
        if comment is not None:
            self.comment = comment
        db.session.commit()

    def is_empty(self):
        return not (self.alerts or self.comment)

    # def update_price(self):
    #     self.price = get_price(self.ticker_id, 0)

    def delete(self):
        for alert in self.alerts:
            alert.delete()
        db.session.delete(self)


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
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

    def edit(self, form):
        self.price = float(form['price'])
        self.price_ticker_id = form['price_ticker_id']
        self.price_usd = self.price / get_price(self.price_ticker_id, 1)
        self.comment = form['comment']

        asset_price = get_price(self.watchlist_asset.ticker_id, 0)
        self.type = 'down' if asset_price >= self.price_usd else 'up'

        db.session.commit()

    def turn_off(self):
        if not self.transaction_id:
            self.status = 'off'

    def turn_on(self):
        if self.transaction_id and self.status != 'on':
            self.transaction_id = None
            self.asset_id = None
        self.status = 'on'

    def delete(self):
        db.session.delete(self)


class PriceHistory(db.Model):
    date = db.Column(db.Date, primary_key=True)
    ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'),
                          primary_key=True)
    price_usd = db.Column(db.Float)
    # Relationships
    ticker = db.relationship('Ticker',
                             backref=db.backref('history', lazy=True))


class UserUtilsMixin:

    def change_currency(self, currency='usd'):
        self.currency = currency
        prefix = current_app.config['CURRENCY_PREFIX']
        self.currency_ticker_id = f'{prefix}{currency}'

    def change_locale(self, locale='en'):
        self.locale = locale

    def create_first_wallet(self):
        wallet = Wallet(name=gettext('Кошелек по умолчанию'))
        asset = WalletAsset(ticker_id=self.currency_ticker_id)
        wallet.wallet_assets.append(asset)
        self.wallets.append(wallet)

    def new_login(self):
        if not self.info:
            self.info.append(UserInfo())

        ip = request.headers.get('X-Real-IP')
        if ip:
            response = requests.get(f'http://ip-api.com/json/{ip}').json()
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
        prefixes = {
            'crypto': current_app.config['CRYPTO_PREFIX'],
            'stocks': current_app.config['STOCKS_PREFIX'],
            'currency': current_app.config['CURRENCY_PREFIX'],
        }

        def get_ticker_id(ticker):
            return ticker.id[len(prefixes[ticker.market]):]

        result = {'wallets': [], 'portfolios': [], 'watchlist': [],
                  'transactions': []}

        # Wallets
        for wallet in self.wallets:
            w = {'id': wallet.id, 'name': wallet.name,
                 'comment': wallet.comment or '', 'assets': []}

            # Wallet Assets
            for asset in wallet.wallet_assets:
                a = {'ticker': {'id': get_ticker_id(asset.ticker),
                                'market': asset.ticker.market},
                     'transactions': []}

                # Transactions
                for t in asset.transactions:
                    a['transactions'].append({
                        'id': t.id,
                        'date': str(t.date),
                        'ticker': {'id': get_ticker_id(t.base_ticker),
                                   'market': t.base_ticker.market},
                        'quantity': t.quantity,
                        'ticker2': {'id': get_ticker_id(t.quote_ticker),
                                    'market': t.quote_ticker.market,
                                    } if t.quote_ticker else None,
                        'quantity2': t.quantity2,
                        'comment': t.comment or '',
                        'type': t.type,
                        'order': t.order,
                        'price': t.price,
                        'price_usd': t.price_usd,
                        'related_transaction_id': t.related_transaction_id,
                        'portfolio_id': t.portfolio.id
                    })

                w['assets'].append(a)
            result['wallets'].append(w)

        # Portfolios
        for portfolio in self.portfolios:
            p = {'id': portfolio.id,
                 'market': portfolio.market,
                 'name': portfolio.name,
                 'comment': portfolio.comment or '',
                 'percent': portfolio.percent or '',
                 'assets': []}

            # Portfolio Assets
            for asset in portfolio.assets:
                p['assets'].append({'ticker': {'id': get_ticker_id(asset.ticker),
                                               'market': asset.ticker.market},
                                    'comment': asset.comment or '',
                                    'percent': asset.percent or ''})
            result['portfolios'].append(p)

        # Watchlist
        for asset in self.watchlist:
            w = {'ticker': {'id': get_ticker_id(asset.ticker),
                            'market': asset.ticker.market},
                 'comment': asset.comment or '',
                 'alerts': []}

            # Alerts
            for alert in asset.alerts:
                w['alerts'].append(
                    {'date': alert.date,
                     'asset_id': alert.asset_id,
                     'price': alert.price,
                     'price_usd': alert.price_usd,
                     'price_ticker': {'symbol': alert.price_ticker.symbol,
                                      'market': alert.price_ticker.market},
                     'type': alert.type,
                     'comment': alert.comment or '',
                     'status': alert.status,
                     'transaction_id': alert.transaction_id})
            result['watchlist'].append(w)

        return result

    def import_data(self, data):
        prefixes = {'crypto': current_app.config['CRYPTO_PREFIX'],
                    'stocks': current_app.config['STOCKS_PREFIX'],
                    'currency': current_app.config['CURRENCY_PREFIX']}

        def get_ticker_id(t):
            return f"{prefixes[t['market']]}{t['id']}" if t else None

        # Portfolios
        new_portfolios_ids = {}
        for p in data.get('portfolios', []):
            portfolio = Portfolio(market=p['market'],
                                  name=p['name'], comment=p['comment'])
            self.portfolios.append(portfolio)
            db.session.commit()
            new_portfolios_ids[p['id']] = portfolio.id

            # Portfolio assets
            for a in p['assets']:
                asset = Asset(ticker_id=get_ticker_id(a['ticker']),
                              percent=a['percent'] or 0, comment=a['comment'])
                portfolio.assets.append(asset)

        # Wallets
        new_transactions_ids = {}
        for w in data.get('wallets', []):
            wallet = Wallet(name=w['name'], comment=w['comment'])
            self.wallets.append(wallet)

            # Wallet assets
            for a in w['assets']:
                asset = WalletAsset(ticker_id=get_ticker_id(a['ticker']))
                wallet.wallet_assets.append(asset)

                # Transactions
                for t in a['transactions']:
                    transaction = Transaction(
                        date=t['date'],
                        ticker_id=get_ticker_id(t['ticker']),
                        quantity=t['quantity'],
                        ticker2_id=get_ticker_id(t['ticker2']),
                        quantity2=t['quantity2'],
                        comment=t['comment'],
                        type=t['type'],
                        order=t['order'],
                        price=t['price'],
                        price_usd=t['price_usd'],
                        related_transaction_id=t['related_transaction_id'],
                        portfolio_id=new_portfolios_ids[t['portfolio_id']]
                    )
                    asset.transactions.append(transaction)
                    db.session.commit()
                    new_transactions_ids[t['id']] = transaction.id

        # Transactions
        for wallet in self.wallets:
            for t in wallet.transactions:
                t.update_dependencies()

                if t.related_transaction_id:
                    id = new_transactions_ids[t.related_transaction_id]
                    t.related_transaction_id = id

        # Watchlist Assets
        for a in data['watchlist']:
            asset = WatchlistAsset(ticker_id=get_ticker_id(a['ticker']))
            asset.comment = asset['comment']

            self.watchlist.append(asset)

            for al in a['alerts']:
                alert = Alert(
                    date=al['date'],
                    asset_id=al['asset_id'],
                    # watchlist_asset_id=watchlist_asset.id,
                    price=al['price'],
                    price_usd=al['price_usd'],
                    price_ticker_id=al['price_ticker_id'],
                    type=al['type'],
                    comment=al['comment'],
                    status=al['status']
                    )
                asset.alerts.append(alert)

        db.session.commit()


class User(db.Model, UserMixin, UserUtilsMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(255))
    locale = db.Column(db.String(32))
    timezone = db.Column(db.String(32))
    currency = db.Column(db.String(32))
    currency_ticker_id = db.Column(db.String(32), db.ForeignKey('ticker.id'))
    # Relationships
    info = db.relationship('UserInfo',
                           backref=db.backref('user', lazy=True),
                           uselist=False)
    currency_ticker = db.relationship('Ticker', uselist=False)


class UserInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    first_visit = db.Column(db.DateTime, default=datetime.utcnow)
    last_visit = db.Column(db.DateTime, default=datetime.utcnow)
    country = db.Column(db.String(255))
    city = db.Column(db.String(255))
