from __future__ import annotations
from flask import flash
from flask_babel import gettext
from flask_login import current_user
from portfolio_tracker.general_functions import find_by_attr

from ..models import DetailsMixin
from ..user.models import User
from .models import db, OtherAsset, OtherBody, OtherTransaction, Portfolio, \
    Asset, Transaction


def get_portfolio(portfolio_id: int | str | None) -> Portfolio | None:
    return find_by_attr(current_user.portfolios, 'id', portfolio_id)


def get_asset(ticker_id: str | None,
              portfolio: Portfolio | None) -> Asset | None:
    if portfolio:
        return find_by_attr(portfolio.assets, 'ticker_id', ticker_id)


def get_other_asset(asset_id: str | int | None,
                    portfolio: Portfolio | None) -> OtherAsset | None:
    if portfolio:
        return find_by_attr(portfolio.other_assets, 'id', asset_id)


def get_transaction(transaction_id: str | int | None,
                    asset: Asset | OtherAsset | None
                    ) -> Transaction | OtherTransaction | None:
    if asset:
        return find_by_attr(asset.transactions, 'id', transaction_id)


def get_body(body_id: str | int | None,
             asset: OtherAsset | None) -> OtherBody | None:
    if asset:
        return find_by_attr(asset.bodies, 'id', body_id)


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


def actions_in_portfolios(portfolio_id: int, action: str) -> None:
    portfolio = get_portfolio(portfolio_id)
    if not portfolio:
        return

    if 'delete' in action:
        if 'with_contents' not in action and not portfolio.is_empty():
            flash(gettext('В портфеле %(name)s есть транзакции',
                          name=portfolio.name), 'danger')
        else:
            portfolio.delete()


def actions_in_assets(ticker_id: str, action: str,
                      portfolio: Portfolio) -> None:
    asset = get_asset(ticker_id, portfolio)
    if not asset:
        return

    if 'delete' in action:
        if 'with_contents' not in action and not asset.is_empty():
            flash(gettext('В активе %(name)s есть транзакции',
                          name=asset.ticker.name), 'danger')
        else:
            asset.delete()


def actions_in_other_assets(asset_id: int, action: str,
                            portfolio: Portfolio) -> None:
    asset = get_other_asset(asset_id, portfolio)
    if not asset:
        return

    if 'delete' in action:
        if 'with_contents' not in action and not asset.is_empty():
            flash(gettext('Актив %(name)s не пустой',
                          name=asset.name), 'danger')
        else:
            asset.delete()


def actions_in_transactions(transaction_id: int, action: str,
                            asset: Asset | OtherAsset) -> None:
    transaction = get_transaction(transaction_id, asset)
    if not transaction:
        return

    if action == 'delete':
        transaction.delete()

    elif action == 'convert_to_transaction':
        if hasattr(transaction, 'convert_order_to_transaction'):
            transaction.convert_order_to_transaction()


def actions_in_bodies(body_id: int, action: str, asset: OtherAsset) -> None:
    body = get_body(body_id, asset)
    if not body:
        return

    if action == 'delete':
        body.delete()


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
