from flask_login import current_user

from portfolio_tracker.app import db
from portfolio_tracker.models import Details, OtherAsset, OtherBody, \
    Portfolio, Asset, Transaction


def get_portfolio(portfolio_id: int | float | str | None,
                  user=current_user) -> Portfolio | None:
    """Возвращает портфель"""
    if portfolio_id:
        portfolio_id = int(portfolio_id)
        for portfolio in user.portfolios:
            if portfolio.id == portfolio_id:
                return portfolio


def get_asset(portfolio: Portfolio | None,
              ticker_id: str | None, create: bool = False) -> Asset | None:
    """Возвращает актив"""
    if portfolio and ticker_id:
        for asset in portfolio.assets:
            if asset.ticker_id == ticker_id:
                return asset

        if create:
            return create_new_asset(portfolio, ticker_id)


def get_other_asset(portfolio: Portfolio | None,
                    asset_id: int | float | str | None) -> OtherAsset | None:
    """Возвращает актив (other)"""
    if portfolio and asset_id:
        asset_id = int(asset_id)
        for asset in portfolio.other_assets:
            if asset.id == asset_id:
                return asset


def get_transaction(asset: Asset, transaction_id: int | float | str | None
                    ) -> Transaction | None:
    """Возвращает транзакцию"""
    if asset and transaction_id:
        transaction_id = int(transaction_id)
        for transaction in asset.transactions:
            if transaction.id == transaction_id:
                return transaction


def get_other_body(asset: Asset,
                   body_id: int | float | str | None) -> OtherBody | None:
    """Возвращает тело актива"""
    if asset and body_id:
        for body in asset.bodies:
            if body.id == int(body_id):
                return body


def create_new_portfolio(form: dict, user=current_user) -> Portfolio:
    """Возвращает новый портфель"""
    portfolio = Portfolio(market=form.get('market'))
    user.portfolios.append(portfolio)
    return portfolio


def create_new_asset(portfolio: Portfolio, ticker_id: str) -> Asset:
    """Возвращает новый актив"""
    asset = Asset(ticker_id=ticker_id)
    portfolio.assets.append(asset)
    db.session.commit()
    return asset


def create_new_transaction(asset: Asset) -> Transaction:
    """Возвращает новую транзакцию."""
    transaction = Transaction(portfolio_id=asset.portfolio_id)
    asset.transactions.append(transaction)
    db.session.commit()
    return transaction


class AllPortfolios(Details):
    """Класс объединяет все портфели пользователя."""

    def __init__(self):
        self.amount = 0
        self.cost_now = 0
        self.in_orders = 0
        for portfolio in current_user.portfolios:
            portfolio.update_price()
            portfolio.update_details()
            self.amount += portfolio.amount
            self.cost_now += portfolio.cost_now
            self.in_orders += portfolio.in_orders
        self.update_details()
