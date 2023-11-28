from flask_login import current_user
from portfolio_tracker.models import Alert, WatchlistAsset
from portfolio_tracker.app import db


def get_watchlist_asset(ticker_id, create=False, user=current_user):
    if ticker_id:
        for asset in user.watchlist:
            if asset.ticker_id == ticker_id:
                return asset

        if create:
            return create_new_watchlist_asset(ticker_id, user)


def get_alert(whitelist_asset, alert_id):
    if whitelist_asset and alert_id:
        for alert in whitelist_asset.alerts:
            if alert.id == int(alert_id):
                return alert


def create_new_watchlist_asset(ticker_id, user=current_user):
    asset = WatchlistAsset(ticker_id=ticker_id)
    user.watchlist.append(asset)
    return asset


def create_new_alert(watchlist_asset):
    alert = Alert()
    watchlist_asset.alerts.append(alert)
    return alert
