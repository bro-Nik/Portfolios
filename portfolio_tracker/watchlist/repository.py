from .models import Alert, Watchlist, WatchlistAsset
from ..app import db


class WatchlistRepository:

    @classmethod
    def get_with_market(cls, user_id, market, status) -> Watchlist:
        watchlist = Watchlist()

        select = (db.select(WatchlistAsset).distinct()
                    .filter_by(user_id=user_id)
                    .join(WatchlistAsset.ticker).filter_by(market=market))

        if status:
            select = select.join(WatchlistAsset.alerts).filter_by(status=status)

        watchlist.assets = tuple(db.session.execute(select).scalars())
        return watchlist


class AssetRepository:

    @staticmethod
    def create() -> WatchlistAsset:
        """Возвращает новый актив"""
        return WatchlistAsset()

    @staticmethod
    def save(asset: WatchlistAsset) -> None:
        if not asset.id:
            db.session.add(asset)
        db.session.commit()

    @staticmethod
    def delete(asset: WatchlistAsset) -> None:
        db.session.delete(asset)
        db.session.commit()


class AlertRepository:

    @staticmethod
    def create() -> Alert:
        """Возвращает новый алерт"""
        alert = Alert()
        return alert

    @staticmethod
    def save(alert: Alert) -> None:
        if not alert.id:
            db.session.add(alert)
        db.session.commit()

    @staticmethod
    def delete(alert: Alert) -> None:
        db.session.delete(alert)
        db.session.commit()
