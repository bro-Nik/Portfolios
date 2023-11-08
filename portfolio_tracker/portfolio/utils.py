from flask_login import current_user

from portfolio_tracker.app import db
from portfolio_tracker.models import Details, Portfolio, Asset, Transaction


def get_portfolio(id, user=current_user):
    if id:
        for portfolio in user.portfolios:
            if portfolio.id == int(id):
                return portfolio


def get_asset(portfolio, ticker_id, create=False):
    if portfolio and ticker_id:
        for asset in portfolio.assets:
            if asset.ticker_id == ticker_id:
                return asset
        else:
            if create:
                return create_new_asset(portfolio, ticker_id)


def get_other_asset(portfolio, asset_id):
    if portfolio and asset_id:
        for asset in portfolio.other_assets:
            if asset.id == int(asset_id):
                return asset


def get_transaction(asset, transaction_id):
    if asset and transaction_id:
        for transaction in asset.transactions:
            if transaction.id == int(transaction_id):
                return transaction


def get_other_body(asset, body_id):
    if asset and body_id:
        for body in asset.bodies:
            if body.id == int(body_id):
                return body


def create_new_portfolio(form, user=current_user):
    portfolio = Portfolio(market=form.get('market'))
    user.portfolios.append(portfolio)
    return portfolio


def create_new_asset(portfolio, ticker_id):
    asset = Asset(ticker_id=ticker_id)
    portfolio.assets.append(asset)
    db.session.commit()
    return asset


def create_new_transaction(asset):
    transaction = Transaction(portfolio_id=asset.portfolio_id)
    asset.transactions.append(transaction)
    db.session.commit()
    return transaction


class AllPortfolios(Details):
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
