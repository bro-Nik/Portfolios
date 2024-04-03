from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List
from flask import flash
from flask_babel import gettext

from flask_login import current_user
from sqlalchemy.orm import Mapped

from ..app import db
from ..models import TransactionsMixin
from ..general_functions import find_by_attr

if TYPE_CHECKING:
    from ..portfolio.models import Transaction
    from ..user.models import User


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

    @classmethod
    def get(cls, wallet_id: int | str | None,
            user: User = current_user) -> Wallet | None:
        return find_by_attr(user.wallets, 'id', wallet_id)

    @classmethod
    def create(cls, user: User = current_user, first=False) -> Wallet:
        wallet = Wallet(name=gettext('Кошелек по умолчанию') if first else '')
        wallet.create_asset(user.currency_ticker)
        return wallet

    @staticmethod
    def last(transaction_type: str) -> Wallet:
        date = result = None

        for wallet in current_user.wallets:
            transaction = wallet.last_transaction(transaction_type)
            if transaction:
                if not date or date < transaction.date:
                    date = transaction.date
                    result = wallet

        return result if result else current_user.wallets[-1]

    @staticmethod
    def get_has_asset(ticker_id: str | None) -> Wallet | None:
        for wallet in current_user.wallets:
            asset = wallet.get_asset(ticker_id)
            if asset and asset.free > 0:
                return wallet

    def edit(self, form: dict) -> None:
        name = form.get('name')
        comment = form.get('comment', '')

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

    @property
    def is_empty(self) -> bool:
        return not (self.wallet_assets or self.transactions or self.comment)

    def update_price(self) -> None:
        self.cost_now = 0
        self.in_orders = 0
        self.free = 0
        self.assets = []
        self.stable_assets = []

        for asset in self.wallet_assets:
            # Стейблкоины и валюта
            if asset.ticker.stable:
                self.stable_assets.append(asset)
                self.free += asset.free * asset.price
                self.in_orders += asset.buy_orders * asset.price
            # Активы
            else:
                self.assets.append(asset)
            self.cost_now += asset.cost_now

    def get_asset(self, find_by: str | int | None):
        if find_by:
            try:
                return find_by_attr(self.wallet_assets, 'id', int(find_by))
            except ValueError:
                return find_by_attr(self.wallet_assets, 'ticker_id', find_by)

    def create_asset(self, ticker: Ticker) -> WalletAsset:
        asset = WalletAsset(ticker_id=ticker.id,
                            ticker=ticker,
                            wallet=self,
                            wallet_id=self.id,
                            quantity=0,
                            buy_orders=0,
                            sell_orders=0)
        return asset

    def last_transaction(self, transaction_type: str) -> Transaction | None:
        transaction_type = transaction_type.lower()
        for transaction in self.transactions:
            if transaction.type.lower() == transaction_type:
                return transaction

    def delete_if_empty(self) -> None:
        if self.is_empty:
            self.delete()
        else:
            flash(gettext('Кошелек %(name)s не пустой',
                          name=self.name), 'danger')

    def delete(self) -> None:
        for asset in self.wallet_assets:
            asset.delete()
        current_user.wallets.remove(self)
        db.session.delete(self)


class WalletAsset(db.Model, TransactionsMixin):
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

    @property
    def is_empty(self) -> bool:
        return not self.transactions

    @property
    def price(self):
        return self.ticker.price

    @property
    def cost_now(self):
        return self.quantity * self.price

    @property
    def free(self) -> float:
        if self.ticker.stable:
            return self.quantity - self.buy_orders
        return self.quantity - self.sell_orders

    def recalculate(self) -> None:
        self.quantity = 0
        self.buy_orders = 0
        self.sell_orders = 0

        for t in self.transactions:
            is_base_asset = bool(self.ticker_id == t.ticker_id)

            if not t.order:
                quantity = 'quantity' if is_base_asset else 'quantity2'
                self.quantity += getattr(t, quantity)

            else:
                if t.type == 'Buy':
                    if is_base_asset:
                        self.buy_orders += t.quantity * t.price_usd
                    else:
                        self.buy_orders -= t.quantity2
                else:
                    if is_base_asset:
                        self.sell_orders -= t.quantity

    def create_transaction(self) -> Transaction:
        """Возвращает новую транзакцию."""
        from ..portfolio.models import Transaction
        transaction = Transaction(
            type='Input' if self.ticker.stable else 'TransferOut',
            ticker_id=self.ticker_id,
            base_ticker=self.ticker,
            date=datetime.now(timezone.utc),
            wallet_id=self.wallet_id,
            quantity=0
        )

        return transaction

    def delete_if_empty(self) -> None:
        if self.is_empty:
            self.delete()
        else:
            flash(gettext('В активе %(name)s есть транзакции',
                          name=self.ticker.name), 'danger')

    def delete(self) -> None:
        for transaction in self.transactions:
            transaction.delete()
        db.session.delete(self)
