from __future__ import annotations
from typing import TYPE_CHECKING

from flask_babel import gettext
from flask_login import current_user

from ..models import DetailsMixin
from ..general_functions import find_by_attr
from .models import Wallet, WalletAsset


if TYPE_CHECKING:
    from ..portfolio.models import Ticker


def get_wallet(wallet_id: int | str | None) -> Wallet | None:
    return find_by_attr(current_user.wallets, 'id', wallet_id)


def get_wallet_has_asset(ticker_id: str | None) -> Wallet | None:
    for wallet in current_user.wallets:
        asset = get_wallet_asset(wallet=wallet, ticker_id=ticker_id)
        if asset and asset.free > 0:
            return wallet


def get_wallet_asset(asset_id: str | int | None = None,
                     wallet: Wallet | None = None,
                     ticker_id: str | None = None) -> WalletAsset | None:
    if wallet:
        if asset_id:
            return find_by_attr(wallet.wallet_assets, 'id', asset_id)
        if ticker_id:
            return find_by_attr(wallet.wallet_assets, 'ticker_id', ticker_id)


def last_wallet(transaction_type: str) -> Wallet:
    date = result = None

    for wallet in current_user.wallets:
        transaction = last_wallet_transaction(wallet, transaction_type)
        if transaction:
            if not date or date < transaction.date:
                date = transaction.date
                result = wallet

    return result if result else current_user.wallets[-1]


def last_wallet_transaction(wallet: Wallet | None,
                            transaction_type: str) -> Transaction | None:
    if wallet:
        transaction_type = transaction_type.lower()
        for transaction in wallet.transactions:
            if transaction.type.lower() == transaction_type:
                return transaction


def create_wallet(user: User = current_user, first=False) -> Wallet:
    wallet = Wallet(name=gettext('Кошелек по умолчанию') if first else '')
    create_wallet_asset(wallet, user.currency_ticker_id)
    user.wallets.append(wallet)
    return wallet


def create_wallet_asset(wallet: Wallet, ticker: Ticker) -> WalletAsset:
    asset = WalletAsset(ticker_id=ticker.id, ticker=ticker, quantity=0)
    wallet.wallet_assets.append(asset)
    return asset


class Wallets(DetailsMixin):
    def __init__(self):
        super().__init__()
        for wallet in current_user.wallets:
            wallet.update_price()
            self.cost_now += wallet.cost_now
            self.in_orders += wallet.in_orders
            self.free += wallet.free
