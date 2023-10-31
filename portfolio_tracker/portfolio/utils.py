# import json
# from datetime import datetime
# from flask import flash, render_template, session, url_for, request, Blueprint
# from flask_babel import gettext
from flask_login import login_required, current_user

from portfolio_tracker.app import db
# from portfolio_tracker.general_functions import get_price, get_price_list
from portfolio_tracker.models import Details, Portfolio, Asset
        # OtherTransaction, OtherBody, Transaction
# from portfolio_tracker.user.utils import from_user_datetime
# from portfolio_tracker.wallet.wallet import get_wallet_has_asset, last_wallet, last_wallet_transaction
# from portfolio_tracker.watchlist.watchlist import get_watchlist_asset
# from portfolio_tracker.wraps import demo_user_change


def get_portfolio(id):
    if id:
        for portfolio in current_user.portfolios:
            if portfolio.id == int(id):
                return portfolio


def get_asset(portfolio, ticker_id, create=False):
    if portfolio and ticker_id:
        for asset in portfolio.assets:
            if asset.ticker_id == ticker_id:
                return asset
        else:
            if create:
                asset = Asset(ticker_id=ticker_id)
                portfolio.assets.append(asset)
                db.session.commit()
                return asset


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


def portfolio_settings_edit(portfolio, form, user=current_user):
    name = form.get('name')
    comment = form.get('comment')
    market = form.get('market')
    percent = form.get('percent') or 0

    if portfolio is None:
        user_portfolios = user.portfolios
        names = [i.name for i in user_portfolios if i.market == market]
        if name in names:
            n = 2
            while str(name) + str(n) in names:
                n += 1
            name = str(name) + str(n)
        portfolio = Portfolio(market=market)
        user.portfolios.append(portfolio)

    if name is not None:
        portfolio.name = name
    portfolio.percent = percent
    portfolio.comment = comment
    db.session.commit()


def asset_settings_edit(asset, form):
    if asset:
        comment = form.get('comment')
        percent = form.get('percent')

        if comment != None:
            asset.comment = comment
        if percent != None:
            asset.percent = percent
        db.session.commit()


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
