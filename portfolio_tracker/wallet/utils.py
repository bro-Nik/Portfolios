from flask_login import current_user
from portfolio_tracker.app import db
from portfolio_tracker.models import Transaction, Wallet, WalletAsset


def get_wallet(wallet_id, user=current_user):
    if wallet_id:
        for wallet in user.wallets:
            if wallet.id == int(wallet_id):
                return wallet


def get_wallet_has_asset(ticker_id, user=current_user):
    for wallet in user.wallets:
        asset = get_wallet_asset(wallet, ticker_id)
        if asset:
            asset.update_price()
            if asset.free > 0:
                return wallet


def get_wallet_asset(wallet, ticker_id, create=False):
    if wallet and ticker_id:
        for asset in wallet.wallet_assets:
            if asset.ticker_id == ticker_id:
                return asset
        else:
            if create:
                return create_new_wallet_asset(wallet, ticker_id)


def get_transaction(asset, transaction_id):
    if transaction_id and asset:
        for transaction in asset.transactions:
            if transaction.id == int(transaction_id):
                return transaction


def last_wallet(transaction_type, user=current_user):
    date = result = None

    for wallet in user.wallets:
        transaction = last_wallet_transaction(wallet, transaction_type)
        if transaction:
            if not date or date < transaction.date:
                date = transaction.date
                result = wallet
    return result


def last_wallet_transaction(wallet, transaction_type):
    for transaction in wallet.transactions:
        if transaction.type.lower() == transaction_type.lower():
            return transaction


def create_new_wallet(user=current_user):
    wallet = Wallet()
    user.wallets.append(wallet)
    return wallet


def create_new_wallet_asset(wallet, ticker_id):
    asset = WalletAsset(ticker_id=ticker_id)
    wallet.wallet_assets.append(asset)
    db.session.commit()
    return asset


def create_new_transaction(asset):
    transaction = Transaction(wallet_id=asset.wallet_id)
    asset.transactions.append(transaction)
    # db.session.commit()
    return transaction


class AllWallets:
    def __init__(self):
        self.cost_now = 0
        self.in_orders = 0
        self.free = 0

        for wallet in current_user.wallets:
            wallet.update_price()
            self.cost_now += wallet.cost_now
            self.in_orders += wallet.in_orders
            self.free += wallet.free
