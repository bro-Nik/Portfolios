from __future__ import annotations
from flask_login import current_user
from portfolio_tracker.general_functions import find_by_attr

from ..models import DetailsMixin
from ..user.models import User
from .models import Ticker, db, OtherAsset, OtherBody, OtherTransaction, Portfolio, \
    Asset, Transaction


def get_portfolio(portfolio_id: int | str | None) -> Portfolio | None:
    return find_by_attr(current_user.portfolios, 'id', portfolio_id)


def get_asset(asset_id: str | int | None,
              portfolio: Portfolio | None = None,
              ticker_id: str | None = None) -> Asset | OtherAsset | None:
    if not portfolio:
        return
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


def create_new_portfolio(user: User = current_user  # type: ignore
                         ) -> Portfolio:
    """Возвращает новый портфель"""
    portfolio = Portfolio()
    user.portfolios.append(portfolio)
    return portfolio


def create_new_asset(portfolio: Portfolio, ticker: Ticker | None = None
                     ) -> Asset | OtherAsset:
    """Возвращает новый актив"""
    if portfolio.market == 'other':
        asset = OtherAsset()
        portfolio.other_assets.append(asset)
    else:
        asset = Asset(ticker=ticker)
        portfolio.assets.append(asset)
    db.session.flush()
    return asset


def create_new_transaction(asset: Asset | WalletAsset) -> Transaction:
    """Возвращает новую транзакцию."""
    transaction = Transaction(ticker_id=asset.ticker_id)
    if hasattr(asset, 'portfolio_id'):
        transaction.portfolio_id = asset.portfolio_id
    if hasattr(asset, 'wallet_id'):
        transaction.wallet_id = asset.wallet_id

    db.session.add(transaction)
    db.session.commit()
    return transaction


def create_new_other_transaction(asset: OtherAsset) -> OtherTransaction:
    """Возвращает новую транзакцию."""
    transaction = OtherTransaction()
    asset.transactions.append(transaction)
    db.session.commit()
    return transaction


def create_new_other_body(asset: OtherAsset) -> OtherBody:
    """Возвращает новое тело актива."""
    body = OtherBody()
    asset.bodies.append(body)
    db.session.commit()
    return body


class Portfolios(DetailsMixin):
    """Класс объединяет все портфели пользователя."""
    def update_price(self):
        for portfolio in current_user.portfolios:
            portfolio.update_price()
            portfolio.update_details()
            self.amount += portfolio.amount
            self.cost_now += portfolio.cost_now
            self.in_orders += portfolio.in_orders
        self.update_details()
