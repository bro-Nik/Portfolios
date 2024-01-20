from __future__ import annotations
from typing import List
from datetime import datetime, timezone
import requests

from flask import current_app, request
from flask_login import UserMixin
from sqlalchemy.orm import Mapped
from werkzeug.security import check_password_hash, generate_password_hash

from ..app import db


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email: str = db.Column(db.String(255), nullable=False, unique=True)
    password: str = db.Column(db.String(255), nullable=False)
    type: str = db.Column(db.String(255))
    locale: str = db.Column(db.String(32))
    timezone: str = db.Column(db.String(32))
    currency: str = db.Column(db.String(32))
    currency_ticker_id: str = db.Column(db.String(32),
                                        db.ForeignKey('ticker.id'))

    # Relationships
    currency_ticker: Mapped[Ticker] = db.relationship(
        'Ticker', uselist=False)
    portfolios: Mapped[List[Portfolio]] = db.relationship(
        'Portfolio', backref=db.backref('user', lazy=True))
    wallets: Mapped[List[Wallet]] = db.relationship(
        'Wallet', backref=db.backref('user', lazy=True))
    watchlist: Mapped[List[WatchlistAsset]] = db.relationship(
        'WatchlistAsset', backref=db.backref('user', lazy=True))
    info: Mapped[UserInfo] = db.relationship(
        'UserInfo', backref=db.backref('user', lazy=True), uselist=False)

    def set_password(self, password: str) -> None:
        """Изменение пароля пользователя."""
        self.password = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Проверка пароля пользователя."""
        return check_password_hash(self.password, password)

    def change_currency(self, currency: str = 'usd') -> None:
        self.currency = currency
        prefix = current_app.config['CURRENCY_PREFIX']
        self.currency_ticker_id = f'{prefix}{currency}'

    def change_locale(self, locale: str = 'en') -> None:
        self.locale = locale

    def new_login(self) -> None:
        ip = request.headers.get('X-Real-IP')
        if ip:
            response = requests.get(f'http://ip-api.com/json/{ip}').json()
            if response.get('status') == 'success':
                self.info.country = response.get('country')
                self.info.city = response.get('city')

    def update_assets(self) -> None:
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

    def cleare(self) -> None:

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

    def delete(self) -> None:
        self.cleare()
        if self.info:
            db.session.delete(self.info)

        db.session.delete(self)
        db.session.commit()

    def make_admin(self) -> None:
        self.type = 'admin'

    def unmake_admin(self) -> None:
        self.type = ''

    def export_data(self) -> None:
        pass

    def import_data(self, data: dict) -> None:
        pass
        # prefixes = {'crypto': current_app.config['CRYPTO_PREFIX'],
        #             'stocks': current_app.config['STOCKS_PREFIX'],
        #             'currency': current_app.config['CURRENCY_PREFIX']}
        #
        # def get_ticker_id(t):
        #     return f"{prefixes[t['market']]}{t['id']}" if t else None
        #
        # # Portfolios
        # new_portfolios_ids = {}
        # for p in data.get('portfolios', []):
        #     portfolio = Portfolio(market=p['market'],
        #                           name=p['name'], comment=p['comment'])
        #     self.portfolios.append(portfolio)
        #     db.session.commit()
        #     new_portfolios_ids[p['id']] = portfolio.id
        #
        #     # Portfolio assets
        #     for a in p['assets']:
        #         asset = Asset(ticker_id=get_ticker_id(a['ticker']),
        #                       percent=a['percent'] or 0, comment=a['comment'])
        #         portfolio.assets.append(asset)
        #
        # # Wallets
        # new_transactions_ids = {}
        # for w in data.get('wallets', []):
        #     wallet = Wallet(name=w['name'], comment=w['comment'])
        #     self.wallets.append(wallet)
        #
        #     # Wallet assets
        #     for a in w['assets']:
        #         asset = WalletAsset(ticker_id=get_ticker_id(a['ticker']))
        #         wallet.wallet_assets.append(asset)
        #
        #         # Transactions
        #         for t in a['transactions']:
        #             transaction = Transaction(
        #                 date=t['date'],
        #                 ticker_id=get_ticker_id(t['ticker']),
        #                 quantity=t['quantity'],
        #                 ticker2_id=get_ticker_id(t['ticker2']),
        #                 quantity2=t['quantity2'],
        #                 comment=t['comment'],
        #                 type=t['type'],
        #                 order=t['order'],
        #                 price=t['price'],
        #                 price_usd=t['price_usd'],
        #                 related_transaction_id=t['related_transaction_id'],
        #                 portfolio_id=new_portfolios_ids[t['portfolio_id']]
        #             )
        #             asset.transactions.append(transaction)
        #             db.session.commit()
        #             new_transactions_ids[t['id']] = transaction.id
        #
        # # Transactions
        # for wallet in self.wallets:
        #     for t in wallet.transactions:
        #         t.update_dependencies()
        #
        #         if t.related_transaction_id:
        #             id = new_transactions_ids[t.related_transaction_id]
        #             t.related_transaction_id = id
        #
        # # Watchlist Assets
        # for a in data['watchlist']:
        #     asset = WatchlistAsset(ticker_id=get_ticker_id(a['ticker']))
        #     asset.comment = asset['comment']
        #
        #     self.watchlist.append(asset)
        #
        #     for al in a['alerts']:
        #         alert = Alert(
        #             date=al['date'],
        #             asset_id=al['asset_id'],
        #             # watchlist_asset_id=watchlist_asset.id,
        #             price=al['price'],
        #             price_usd=al['price_usd'],
        #             price_ticker_id=al['price_ticker_id'],
        #             type=al['type'],
        #             comment=al['comment'],
        #             status=al['status']
        #             )
        #         asset.alerts.append(alert)
        #
        # db.session.commit()


class UserInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey('user.id'))
    first_visit: datetime = db.Column(db.DateTime,
                                      default=datetime.now(timezone.utc))
    last_visit: datetime = db.Column(db.DateTime,
                                     default=datetime.now(timezone.utc))
    country: str = db.Column(db.String(255))
    city: str = db.Column(db.String(255))