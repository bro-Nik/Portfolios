from __future__ import annotations

from flask_login import current_user

from ..models import DetailsMixin
from ..general_functions import find_by_attr
from .models import db, Wallet, WalletAsset


def get_wallet(wallet_id: int | str | None) -> Wallet | None:
    return find_by_attr(current_user.wallets, 'id', wallet_id)


def get_wallet_has_asset(ticker_id: str | None) -> Wallet | None:
    for wallet in current_user.wallets:
        asset = get_wallet_asset(None, wallet, ticker_id)
        if asset:
            asset.update_price()
            if asset.free > 0:
                return wallet


def get_wallet_asset(asset_id: str | int | None, wallet: Wallet | None,
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
        for transaction in wallet.transactions:
            if transaction.type.lower() == transaction_type.lower():
                return transaction


def create_new_wallet(user: User = current_user) -> Wallet:
    wallet = Wallet()
    create_new_wallet_asset(wallet, user.currency_ticker)
    user.wallets.append(wallet)
    # db.session.flush()

    return wallet


def create_new_wallet_asset(wallet: Wallet, ticker: Ticker) -> WalletAsset:
    asset = WalletAsset(ticker_id=ticker.id)
    wallet.wallet_assets.append(asset)
    return asset


class Wallets(DetailsMixin):
    def update_price(self):
        for wallet in current_user.wallets:
            wallet.update_price()
            self.cost_now += wallet.cost_now
            self.in_orders += wallet.in_orders
            self.free += wallet.free
