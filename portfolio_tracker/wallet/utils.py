from __future__ import annotations

from flask import flash
from flask_babel import gettext
from flask_login import current_user

from ..models import DetailsMixin
from ..general_functions import find_by_id
from .models import db, Wallet, WalletAsset


def get_wallet(wallet_id: int | str | None,
               user: User = current_user) -> Wallet | None:  # type: ignore
    if wallet_id:
        return find_by_id(user.wallets, int(wallet_id))


def get_wallet_has_asset(ticker_id: str | None,
                         user: User = current_user  # type: ignore
                         ) -> Wallet | None:
    for wallet in user.wallets:
        asset = get_wallet_asset(wallet, ticker_id)
        if asset:
            asset.update_price()
            if asset.free > 0:
                return wallet


def get_wallet_asset(wallet: Wallet | None, ticker_id: str | None,
                     create: bool = False) -> WalletAsset | None:
    if wallet and ticker_id:
        for asset in wallet.wallet_assets:
            if asset.ticker_id == ticker_id:
                return asset

        if create:
            return create_new_wallet_asset(wallet, ticker_id)


def get_transaction(asset: Asset | WalletAsset | None,
                    transaction_id: int | str | None) -> Transaction | None:
    if transaction_id and asset:
        return find_by_id(asset.transactions, int(transaction_id))


def last_wallet(transaction_type: str,
                user: User = current_user  # type: ignore
                ) -> Wallet:
    date = result = None

    for wallet in user.wallets:
        transaction = last_wallet_transaction(wallet, transaction_type)
        if transaction:
            if not date or date < transaction.date:
                date = transaction.date
                result = wallet

    return result if result else user.wallets[-1]


def last_wallet_transaction(wallet: Wallet | None,
                            transaction_type: str) -> Transaction | None:
    if wallet:
        for transaction in wallet.transactions:
            if transaction.type.lower() == transaction_type.lower():
                return transaction


def create_new_wallet(user: User = current_user,  # type: ignore
                      name=gettext('Кошелек по умолчанию'),
                      **kwargs) -> Wallet:
    wallet = Wallet(name=name, **kwargs)
    create_new_wallet_asset(wallet, user.currency_ticker_id)
    user.wallets.append(wallet)

    return wallet


def create_new_wallet_asset(wallet: Wallet, ticker_id: str) -> WalletAsset:
    asset = WalletAsset(ticker_id=ticker_id)
    wallet.wallet_assets.append(asset)
    db.session.commit()
    return asset


def actions_on_wallets(ids: list[int | str | None], action: str) -> None:
    for wallet_id in ids:
        wallet = get_wallet(wallet_id)
        if not wallet:
            continue

        if 'delete' in action:
            if 'with_contents' not in action and not wallet.is_empty():
                flash(gettext('Кошелек %(name)s не пустой',
                              name=wallet.name), 'danger')
            else:
                wallet.delete()

    db.session.commit()

    if not current_user.wallets:
        current_user.create_first_wallet()
        db.session.commit()


def actions_on_assets(wallet: Wallet | None, ids: list[str | None],
                      action: str) -> None:
    for ticker_id in ids:
        asset = get_wallet_asset(wallet, ticker_id)
        if not asset:
            continue

        if 'delete' in action:
            if 'with_contents' not in action and not asset.is_empty():
                flash(gettext('В активе %(name)s есть транзакции',
                              name=asset.ticker.name), 'danger')
            else:
                asset.delete()

    db.session.commit()


def actions_on_transactions(asset: WalletAsset | None,
                            ids: list[int | str | None], action: str) -> None:
    for transaction_id in ids:
        transaction = get_transaction(asset, transaction_id)
        if not transaction:
            continue

        if 'delete' in action:
            transaction.delete()

    db.session.commit()


class AllWallets(DetailsMixin):
    def update_price(self):
        for wallet in current_user.wallets:
            wallet.update_price()
            self.cost_now += wallet.cost_now
            self.in_orders += wallet.in_orders
            self.free += wallet.free
