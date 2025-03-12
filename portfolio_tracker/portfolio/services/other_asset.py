from datetime import datetime, timezone

from flask import flash
from flask_babel import gettext

from portfolio_tracker.general_functions import find_by_attr
from portfolio_tracker.portfolio.models import OtherAsset, OtherBody, Transaction
from portfolio_tracker.portfolio.repository import OtherAssetRepository


class OtherAssetService:

    def __init__(self, asset: OtherAsset) -> None:
        self.asset = asset

    def edit(self, form: dict) -> None:
        asset = self.asset
        name = form.get('name')
        comment = form.get('comment')
        percent = form.get('percent')

        if name is not None:
            if asset.name == name:
                n = 2
                while name in [i.name for i in asset.portfolio.other_assets]:
                    name = form['name'] + str(n)
                    n += 1

        if name:
            asset.name = name
        if comment is not None:
            asset.comment = comment
        if percent is not None:
            asset.percent = percent or 0

        OtherAssetRepository.save(self.asset)

    def get_transaction(self, transaction_id: str | int | None):
        return find_by_attr(self.asset.transactions, 'id', transaction_id)

    def create_transaction(self):
        transaction = Transaction()
        transaction.type = 'Profit'
        transaction.amount = 0
        transaction.date = datetime.now(timezone.utc)
        return transaction

    def get_body(self, body_id: str | int | None):
        return find_by_attr(self.asset.bodies, 'id', body_id)

    def create_body(self) -> OtherBody:
        """Возвращает новое тело актива."""
        body = OtherBody()
        body.date = datetime.now(timezone.utc)
        body.asset = self.asset
        return body

    def delete_if_empty(self) -> None:
        if self.asset.is_empty:
            self.delete()
        else:
            flash(gettext('Актив %(name)s не пустой',
                          name=self.asset.name), 'warning')

    def delete(self) -> None:
        for body in self.asset.bodies:
            body.service.delete()
        for transaction in self.asset.transactions:
            transaction.service.delete()
        OtherAssetRepository.delete(self.asset)
