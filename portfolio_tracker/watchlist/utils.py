from flask_login import current_user

from ..general_functions import find_by_id
from ..user.models import User
from .models import db, Alert, WatchlistAsset


def get_watchlist_asset(ticker_id: str | None, create: bool = False,
                        user: User = current_user  # type: ignore
                        ) -> WatchlistAsset | None:
    if ticker_id:
        for asset in user.watchlist:
            if asset.ticker_id == ticker_id:
                return asset

        if create:
            return create_new_watchlist_asset(ticker_id, user)


def get_alert(whitelist_asset: WatchlistAsset | None,
              alert_id: int | str | None) -> Alert | None:
    if whitelist_asset and alert_id:
        return find_by_id(whitelist_asset.alerts, int(alert_id))


def create_new_watchlist_asset(ticker_id: str,
                               user: User = current_user  # type: ignore
                               ) -> WatchlistAsset:
    asset = WatchlistAsset(ticker_id=ticker_id)
    user.watchlist.append(asset)
    return asset


def create_new_alert(watchlist_asset: WatchlistAsset) -> Alert:
    alert = Alert()
    watchlist_asset.alerts.append(alert)
    return alert


def actions_on_watchlist(ids: list[str | None], action: str) -> None:
    for ticker_id in ids:
        watchlist_asset = get_watchlist_asset(ticker_id)

        if not watchlist_asset:
            continue

        if action == 'delete_with_orders':
            watchlist_asset.delete()

        elif action == 'delete':
            for alert in watchlist_asset.alerts:
                if not alert.transaction_id:
                    alert.delete()
            if watchlist_asset.is_empty():
                watchlist_asset.delete()

    db.session.commit()


def actions_on_alerts(watchlist_asset: WatchlistAsset | None,
                      ids: list[int | str | None], action: str) -> None:
    for alert_id in ids:
        alert = get_alert(watchlist_asset, alert_id)
        if not alert:
            continue

        # Delete
        if action == 'delete':
            if not alert.transaction_id:
                alert.delete()

        # Convert to transaction
        elif action == 'convert_to_transaction':
            if alert.transaction:
                alert.transaction.convert_order_to_transaction()

        # Turn off
        elif action == 'turn_off':
            alert.turn_off()

        # Turn on
        elif action == 'turn_on':
            alert.turn_on()

    db.session.commit()
