from flask_login import current_user

from portfolio_tracker.portfolio.models import Asset, OtherAsset, OtherTransaction, Portfolio, Transaction
from portfolio_tracker.portfolio.repository import PortfolioRepository
from portfolio_tracker.user.models import User
from portfolio_tracker.user.repository import UserRepository
from portfolio_tracker.wallet.models import Wallet, WalletAsset
from portfolio_tracker.watchlist.models import Alert, Watchlist, WatchlistAsset
from portfolio_tracker.watchlist.repository import WatchlistRepository


def get_user(user_id: int | None = None, user: User | None = None,
             **kwargs) -> User | None:
    if user_id and current_user.type == 'admin':
        return UserRepository.get(user_id)
    if user:
        return user
    if current_user.is_authenticated:
        return current_user  # type: ignore


def get_portfolio(portfolio_id: int | str | None = None, create=False,
                  **kwargs) -> Portfolio | None:
    user = get_user(**kwargs)
    if user:
        portfolio = user.service.get_portfolio(portfolio_id)

        if not portfolio and create is True:
            portfolio = user.service.create_portfolio()
        return portfolio


def get_wallet(wallet_id: int | str | None = None, create=False,
               **kwargs) -> Wallet | None:
    user = get_user(**kwargs)
    if user:
        wallet = user.service.get_wallet(wallet_id)

        if not wallet and create:
            wallet = user.service.create_wallet()
        return wallet


def get_portfolio_asset(**kwargs) -> Asset | OtherAsset | None:
    return _get_asset(parent=get_portfolio(**kwargs), **kwargs)


def get_wallet_asset(**kwargs) -> WalletAsset | None:
    return _get_asset(parent=get_wallet(**kwargs), **kwargs)


def _get_asset(ticker_id=None, asset_id=None, create=False, parent=None,
               **kwargs):
    if parent:
        asset = parent.service.get_asset(ticker_id or asset_id)

        if not asset and create:
            asset = parent.service.create_asset(ticker_id)
        return asset


def get_body(body_id=None, create=False, **kwargs) -> Asset | None:
    asset = get_portfolio_asset(**kwargs)

    if asset and isinstance(asset, OtherAsset):
        body = asset.service.get_body(body_id)

        if not body and create:
            body = asset.service.create_body()
        return body

def get_portfolio_transaction(transaction_id=None, create=False, **kwargs
                              ) -> Transaction | OtherTransaction | None:
    asset = get_portfolio_asset(**kwargs)
    if asset:
        transaction = asset.service.get_transaction(transaction_id)

        if not transaction and create is True:
            transaction = asset.service.create_transaction()
        return transaction


def get_wallet_transaction(transaction_id=None, create=False, **kwargs
                           ) -> Transaction | None:
    asset = get_wallet_asset(**kwargs)
    if asset:
        transaction = asset.service.get_transaction(transaction_id)

        if not transaction and create is True:
            transaction = asset.service.create_transaction()
        return transaction


def get_watchlist(market=None, status=None, **kwargs) -> Watchlist | None:
    user = get_user(**kwargs)
    if user:
        if market:
            return WatchlistRepository.get_with_market(user.id, market, status)
        return user.service.get_watchlist()


def get_watchlist_asset(create=False, **kwargs) -> WatchlistAsset | None:
    watchlist = get_watchlist(**kwargs)
    if watchlist:
        asset = watchlist.service.get_asset(**kwargs)

        if not asset and create:
            # Если из портфеля, то не создавать, пока нет уведомлений
            save = not kwargs.get('asset_id')
            print(save)

            asset = watchlist.service.create_asset(kwargs.get('ticker_id'), save)

        return asset


def get_alert(alert_id=None, create=False, **kwargs) -> Alert | None:
    asset = get_watchlist_asset(create=True, **kwargs)
    if asset:
        alert = asset.service.get_alert(alert_id)
        if not alert and create:
            alert = asset.service.create_alert()

        return alert
