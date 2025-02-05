from datetime import datetime, timezone

from flask import flash
from flask_babel import gettext

from portfolio_tracker.general_functions import find_by_attr

from ..models import Asset, OtherTransaction, Transaction
from ..repository import AssetRepository, TransactionRepository


class AssetService:

    def __init__(self, asset: Asset) -> None:
        self.asset = asset

    def edit(self, form: dict) -> None:
        comment = form.get('comment')
        percent = form.get('percent')

        if comment is not None:
            self.asset.comment = comment
        if percent is not None:
            self.asset.percent = percent or 0

        AssetRepository.save(self.asset)

    def get_transaction(self, transaction_id: str | int | None):
        return find_by_attr(self.asset.transactions, 'id', transaction_id)

    def create_transaction(self) -> Transaction | OtherTransaction:
        """Возвращает новую транзакцию."""
        transaction = Transaction()

        transaction.type = 'Buy'
        transaction.ticker_id = self.asset.ticker_id
        transaction.base_ticker = self.asset.ticker
        transaction.quantity = 0
        transaction.portfolio_id = self.asset.portfolio_id
        transaction.date = datetime.now(timezone.utc)
        transaction.price = 0

        transaction.portfolio_asset = self.asset
        transaction.portfolio = self.asset.portfolio

        return transaction

    def set_default_data(self):
        self.asset.amount = 0
        self.asset.quantity = 0
        self.asset.sell_orders = 0
        self.asset.buy_orders = 0

    def move_asset_to(self, portfolio_id: str | None = None):
        """Перемещение актива"""
        user = self.asset.portfolio.user

        portfolio = user.service.get_portfolio(portfolio_id)
        if portfolio:
            asset2 = portfolio.service.get_asset(self.asset.ticker_id)

            for transaction in self.asset.transactions:
                transaction.portfolio_id = portfolio.id
                if asset2:
                    self.asset.transactions.remove(transaction)
                    asset2.transactions.append(transaction)
                    transaction.service.update_dependencies()

            if asset2:
                while self.asset.alerts:
                    alert = self.asset.alerts.pop()
                    alert.asset_id = asset2.id
                    asset2.alerts.append(alert)

                asset2.comment = f'{asset2.comment or ""}{self.asset.comment or ""}'
                self.delete()
                AssetRepository.save(asset2)
            else:
                self.asset.portfolio_id = portfolio.id
                AssetRepository.save(self.asset)

    def recalculate(self):
        self.set_default_data()

        for t in self.asset.transactions:
            t.service.update_dependencies()

            # if t.type in ('Buy', 'Sell'):
            #     if self.asset.ticker_id == t.ticker2_id:
            #         # Это котируемый актив
            #         if t.order:
            #             if t.type == 'Buy':
            #                 self.asset.sell_orders -= t.quantity2
            #             elif t.type == 'Sell':
            #                 self.asset.buy_orders -= t.quantity2
            #
            #         else:
            #             self.asset.amount += t.quantity2
            #             self.asset.quantity += t.quantity2
            #
            #     else:
            #         # Это базовый актив
            #         if t.order:
            #             if t.type == 'Sell':
            #                 self.asset.sell_orders -= t.quantity
            #             elif t.type == 'Buy':
            #                 self.asset.buy_orders -= t.quantity
            #             #     w_asset1.sell_orders -= self.quantity * d
            #
            #         else:
            #             self.asset.amount += t.quantity * t.price_usd
            #             self.asset.quantity += t.quantity
            #
            # elif t.type in ('Earning'):
            #     self.asset.quantity += t.quantity
            #
            # elif t.type in ('Input', 'Output'):
            #     self.asset.amount += t.quantity
            #     self.asset.quantity += t.quantity

    def delete_if_empty(self) -> None:
        if self.asset.is_empty:
            self.delete()
        else:
            flash(gettext('В активе %(name)s есть транзакции',
                          name=self.asset.ticker.name), 'warning')

    def delete(self) -> None:
        for transaction in self.asset.transactions:
            transaction.service.delete()

        for alert in self.asset.alerts:
            # отставляем уведомления
            alert.asset_id = None
            alert.comment = gettext('Актив удален из портфеля %(name)s',
                                    name=self.asset.portfolio.name)
        self.alerts = []

        AssetRepository.delete(self.asset)
