from __future__ import annotations
from typing import List
from flask import flash
from flask_babel import gettext

from sqlalchemy.orm import Mapped

from ..app import db


class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey('user.id'))
    name: str = db.Column(db.String(255))
    comment: str = db.Column(db.String(1024))

    # Relationships
    wallet_assets: Mapped[List[WalletAsset]] = db.relationship(
        'WalletAsset', backref=db.backref('wallet', lazy=True))
    transactions: Mapped[List[Transaction]] = db.relationship(
        'Transaction', backref=db.backref('wallet', lazy=True,
                                          order_by='Transaction.date.desc()'))

    def edit(self, form: dict) -> None:
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

    def is_empty(self) -> bool:
        return not (self.wallet_assets or self.transactions or self.comment)

    def update_price(self) -> None:
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

    def delete_if_empty(self) -> None:
        if self.is_empty():
            self.delete()
        else:
            flash(gettext('Кошелек %(name)s не пустой',
                          name=self.name), 'danger')

    def delete(self) -> None:
        for asset in self.wallet_assets:
            asset.delete()
        db.session.delete(self)


class WalletAsset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wallet_id: int = db.Column(db.Integer, db.ForeignKey('wallet.id'))
    ticker_id: str = db.Column(db.String(256), db.ForeignKey('ticker.id'))
    quantity: float = db.Column(db.Float, default=0)
    buy_orders: float = db.Column(db.Float, default=0)
    sell_orders: float = db.Column(db.Float, default=0)

    # Relationships
    ticker: Mapped[Ticker] = db.relationship(
        'Ticker', backref=db.backref('ticker_wallets', lazy=True))
    transactions: Mapped[List[Transaction]] = db.relationship(
        "Transaction",
        primaryjoin="and_(or_(WalletAsset.ticker_id == foreign(Transaction.ticker_id), "
                    "WalletAsset.ticker_id == foreign(Transaction.ticker2_id)), "
                    "WalletAsset.wallet_id == Transaction.wallet_id)",
        viewonly=True,
        backref=db.backref('wallet_asset', lazy=True)
    )

    def is_empty(self) -> bool:
        return not self.transactions

    def update_price(self) -> None:
        self.price = self.ticker.price
        self.cost_now = self.quantity * self.price

        if self.ticker.stable:
            self.free = self.quantity - self.buy_orders
        else:
            self.free = self.quantity - self.sell_orders

    def delete_if_empty(self) -> None:
        if self.is_empty():
            self.delete()
        else:
            flash(gettext('В активе %(name)s есть транзакции',
                          name=self.ticker.name), 'danger')

    def delete(self) -> None:
        for transaction in self.transactions:
            transaction.delete()
        db.session.delete(self)
