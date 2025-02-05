
from portfolio_tracker.general_functions import find_by_attr
from portfolio_tracker.watchlist.models import Alert, WatchlistAsset
from portfolio_tracker.app import db
from portfolio_tracker.watchlist.repository import AssetRepository


class AssetService:

    def __init__(self, asset: WatchlistAsset) -> None:
        self.asset = asset

    def edit(self, form: dict) -> None:
        comment = str(form.get('comment', ''))
        if comment is not None:
            self.asset.comment = comment

        AssetRepository.save(self.asset)

    def get_alert(self, alert_id: int | str | None) -> Alert | None:
        return find_by_attr(self.asset.alerts, 'id', alert_id)

    def create_alert(self) -> Alert:
        alert = Alert()
        return alert

    def delete_if_empty(self) -> None:
        for alert in self.asset.alerts:
            if not alert.transaction_id:
                self.asset.alerts.remove(alert)
                alert.service.delete()
        if self.asset.is_empty:
            self.delete()

    def delete(self) -> None:
        for alert in self.asset.alerts:
            alert.service.delete()
        db.session.delete(self.asset)
