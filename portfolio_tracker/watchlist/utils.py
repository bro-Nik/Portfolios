from __future__ import annotations
from typing import TYPE_CHECKING
from flask_login import current_user

from ..general_functions import find_by_attr
from .models import Alert, WatchlistAsset

if TYPE_CHECKING:
    from ..portfolio.models import Ticker


def get_asset(asset_id: str | int | None = None,
              ticker_id: str | None = None) -> WatchlistAsset | None:
    if asset_id:
        return find_by_attr(current_user.watchlist, 'id', asset_id)
    if ticker_id:
        return find_by_attr(current_user.watchlist, 'ticker_id', ticker_id)


def get_alert(alert_id: int | str | None,
              asset: WatchlistAsset | None) -> Alert | None:
    if asset:
        return find_by_attr(asset.alerts, 'id', alert_id)


def create_watchlist_asset(ticker: Ticker) -> WatchlistAsset:
    asset = WatchlistAsset(ticker=ticker, ticker_id=ticker.id)
    current_user.watchlist.append(asset)
    return asset


def create_alert(asset: WatchlistAsset) -> Alert:
    alert = Alert()
    asset.alerts.append(alert)
    return alert
