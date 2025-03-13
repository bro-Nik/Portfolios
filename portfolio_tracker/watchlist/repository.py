from portfolio_tracker.repository import DefaultRepository
from .models import Alert, Watchlist, WatchlistAsset
from ..app import db


class WatchlistRepository:

    @classmethod
    def get_with_market(cls, user_id, market, status) -> Watchlist:
        select = (db.select(WatchlistAsset).distinct()
                    .filter_by(user_id=user_id)
                    .join(WatchlistAsset.ticker).filter_by(market=market))

        if status:
            select = select.join(WatchlistAsset.alerts).filter_by(status=status)

        watchlist = Watchlist()
        watchlist.assets = tuple(db.session.execute(select).scalars())
        return watchlist


class AssetRepository(DefaultRepository):
    model = WatchlistAsset


class AlertRepository(DefaultRepository):
    model = Alert
