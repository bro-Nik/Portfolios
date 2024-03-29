from __future__ import annotations
from datetime import datetime, timezone

from flask_login import current_user

from ..general_functions import find_by_attr
from ..wallet.models import WalletAsset
from ..models import DetailsMixin
from ..user.models import User
from .models import Ticker, db, OtherAsset, OtherBody, OtherTransaction, \
    Portfolio, Asset, Transaction


def get_portfolio(portfolio_id: int | str | None) -> Portfolio | None:
    return find_by_attr(current_user.portfolios, 'id', portfolio_id)


def get_asset(asset_id: str | int | None = None,
              portfolio: Portfolio | None = None,
              ticker_id: str | None = None) -> Asset | OtherAsset | None:
    if portfolio:
        if portfolio.market == 'other':
            return find_by_attr(portfolio.other_assets, 'id', asset_id)
        if ticker_id:
            return find_by_attr(portfolio.assets, 'ticker_id', ticker_id)
        return find_by_attr(portfolio.assets, 'id', asset_id)


def get_ticker(ticker_id: str | None) -> Ticker | None:
    if ticker_id:
        return db.session.execute(
            db.select(Ticker).filter_by(id=ticker_id)).scalar()


def get_transaction(transaction_id: str | int | None,
                    asset: Asset | OtherAsset | WalletAsset | None
                    ) -> Transaction | OtherTransaction | None:
    if asset:
        return find_by_attr(asset.transactions, 'id', transaction_id)


def get_body(body_id: str | int | None,
             asset: OtherAsset | None) -> OtherBody | None:
    if asset:
        return find_by_attr(asset.bodies, 'id', body_id)


def create_portfolio(user: User = current_user) -> Portfolio:
    """Возвращает новый портфель"""
    portfolio = Portfolio()
    user.portfolios.append(portfolio)
    return portfolio


def create_asset(portfolio: Portfolio, ticker: Ticker) -> Asset:
    """Возвращает новый актив"""
    asset = Asset(ticker=ticker)
    portfolio.assets.append(asset)
    return asset


def create_other_asset(portfolio: Portfolio) -> OtherAsset:
    """Возвращает новый актив"""
    asset = OtherAsset()
    portfolio.other_assets.append(asset)
    return asset


def create_new_transaction(asset: Asset | WalletAsset | OtherAsset
                           ) -> Transaction | OtherTransaction:
    """Возвращает новую транзакцию."""
    if isinstance(asset, Asset):
        transaction = Transaction(type='Buy', ticker_id=asset.ticker_id,
                                  quantity=0, price=asset.price)
    elif isinstance(asset, WalletAsset):
        transaction = Transaction(type='Input' if asset.ticker.stable else 'TransferOut')
    elif isinstance(asset, OtherAsset):
        transaction = OtherTransaction(type='Profit')
        if asset.transactions:
            transaction.amount_ticker = asset.transactions[-1].amount_ticker
        else:
            transaction.amount_ticker = current_user.currency_ticker

    transaction.date = datetime.now(timezone.utc)

    if isinstance(asset, Asset):
        transaction.portfolio_id = asset.portfolio_id
    elif isinstance(asset, WalletAsset):
        transaction.wallet_id = asset.wallet_id

    asset.transactions.append(transaction)
    return transaction


def create_new_body(asset: OtherAsset) -> OtherBody:
    """Возвращает новое тело актива."""
    body = OtherBody()
    body.date = datetime.now(datetime.timezone.utc)
    if asset.bodies:
        body.amount_ticker = asset.bodies[-1].amount_ticker
        body.cost_now_ticker = asset.bodies[-1].cost_now_ticker
    else:
        body.amount_ticker = current_user.currency_ticker
        body.cost_now_ticker = current_user.currency_ticker

    asset.bodies.append(body)
    return body


class Portfolios(DetailsMixin):
    """Класс объединяет все портфели пользователя."""
    def __init__(self):
        super().__init__()
        for portfolio in current_user.portfolios:
            portfolio.update_price()
            self.amount += portfolio.amount
            self.cost_now += portfolio.cost_now
            self.in_orders += portfolio.in_orders
