from __future__ import annotations
from flask import flash
from flask_babel import gettext
from flask_login import current_user
from portfolio_tracker.general_functions import find_by_id

from ..models import DetailsMixin
from ..user.models import User
from .models import db, OtherAsset, OtherBody, OtherTransaction, Portfolio, \
    Asset, Transaction


def get_portfolio(portfolio_id: int | str | None,
                  user: User = current_user  # type: ignore
                  ) -> Portfolio | None:
    """Возвращает портфель"""
    if portfolio_id:
        return find_by_id(user.portfolios, int(portfolio_id))


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
                    asset_id: int | str | None) -> OtherAsset | None:
    """Возвращает актив (other)"""
    if portfolio and asset_id:
        return find_by_id(portfolio.other_assets, int(asset_id))


def get_transaction(asset: Asset | None,
                    transaction_id: int | str | None) -> Transaction | None:
    """Возвращает транзакцию"""
    if asset and transaction_id:
        return find_by_id(asset.transactions, int(transaction_id))


def get_other_transaction(asset: OtherAsset | None,
                          transaction_id: int | str | None
                          ) -> OtherTransaction | None:
    if asset and transaction_id:
        return find_by_id(asset.transactions, int(transaction_id))


def get_other_body(asset: OtherAsset | None,
                   body_id: int | str | None) -> OtherBody | None:
    """Возвращает тело актива"""
    if asset and body_id:
        return find_by_id(asset.bodies, int(body_id))


def create_new_portfolio(form: dict,
                         user: User = current_user  # type: ignore
                         ) -> Portfolio:
    """Возвращает новый портфель"""
    portfolio = Portfolio()
    portfolio.market = form.get('market')
    user.portfolios.append(portfolio)
    return portfolio


def create_new_asset(portfolio: Portfolio, ticker_id: str) -> Asset:
    """Возвращает новый актив"""
    asset = Asset(ticker_id=ticker_id)
    portfolio.assets.append(asset)
    db.session.commit()
    return asset


def create_new_other_asset(portfolio: Portfolio) -> OtherAsset:
    """Возвращает новый актив пита другой"""
    asset = OtherAsset()
    portfolio.other_assets.append(asset)
    db.session.commit()
    return asset


def create_new_transaction(asset: Asset | WalletAsset) -> Transaction:
    """Возвращает новую транзакцию."""
    transaction = Transaction(portfolio_id=asset.portfolio_id,
                              wallet_id=asset.wallet_id,
                              ticker_id=asset.ticker_id)
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


def actions_on_portfolios(ids: list[int | str | None], action: str) -> None:
    for portfolio_id in ids:
        portfolio = get_portfolio(portfolio_id)
        if not portfolio:
            continue

        if 'delete' in action:
            if 'with_contents' not in action and not portfolio.is_empty():
                flash(gettext('В портфеле %(name)s есть транзакции',
                              name=portfolio.name), 'danger')
            else:
                portfolio.delete()

    db.session.commit()


def actions_on_assets(portfolio: Portfolio | None, ids: list[str | None],
                      action: str) -> None:
    for ticker_id in ids:
        asset = get_asset(portfolio, ticker_id)
        if not asset:
            continue

        if 'delete' in action:
            if 'with_contents' not in action and not asset.is_empty():
                flash(gettext('В активе %(name)s есть транзакции',
                              name=asset.ticker.name), 'danger')
            else:
                asset.delete()

    db.session.commit()


def actions_on_transactions(asset: Asset | None, ids: list[int | str | None],
                            action: str) -> None:
    for transaction_id in ids:
        transaction = get_transaction(asset, transaction_id)
        if not transaction:
            continue

        if action == 'delete':
            transaction.delete()

        elif action == 'convert_to_transaction':
            if hasattr(transaction, 'convert_order_to_transaction'):
                transaction.convert_order_to_transaction()

    db.session.commit()


def actions_on_other_assets(portfolio: Portfolio | None,
                            ids: list[int | str | None], action: str) -> None:
    for asset_id in ids:
        asset = get_other_asset(portfolio, asset_id)
        if not asset:
            continue

        if 'delete' in action:
            if 'with_contents' not in action and not asset.is_empty():
                flash(gettext('Актив %(name)s не пустой',
                              name=asset.name), 'danger')
            else:
                asset.delete()

    db.session.commit()


def actions_on_other_transactions(asset: OtherAsset | None,
                                  ids: list[int | str | None],
                                  action: str) -> None:
    for transaction_id in ids:
        transaction = get_other_transaction(asset, transaction_id)
        if not transaction:
            continue

        if action == 'delete':
            transaction.delete()

    db.session.commit()


def actions_on_other_body(asset: OtherAsset | None,
                          ids: list[int | str | None],
                          action: str) -> None:
    for body_id in ids:
        body = get_other_body(asset, body_id)
        if not body:
            continue

        if action == 'delete':
            body.delete()

    db.session.commit()


class AllPortfolios(DetailsMixin):
    """Класс объединяет все портфели пользователя."""
    def update_price(self):
        for portfolio in current_user.portfolios:
            portfolio.update_price()
            portfolio.update_details()
            self.amount += portfolio.amount
            self.cost_now += portfolio.cost_now
            self.in_orders += portfolio.in_orders
        self.update_details()
