from datetime import datetime, timezone
from portfolio_tracker.general_functions import find_by_attr
from portfolio_tracker.portfolio.models import Transaction
from portfolio_tracker.portfolio.repository import TransactionRepository
from portfolio_tracker.wallet.models import WalletAsset
from portfolio_tracker.wallet.repository import WalletAssetRepository


class AssetService:
    def __init__(self, asset: WalletAsset) -> None:
        self.asset = asset

    def set_default_data(self):
        self.asset.quantity = 0
        self.asset.buy_orders = 0
        self.asset.sell_orders = 0

    def recalculate(self) -> None:
        self.set_default_data()

        for t in self.asset.transactions:
            is_base_asset = bool(self.asset.ticker_id == t.ticker_id)

            if not t.order:
                quantity = 'quantity' if is_base_asset else 'quantity2'
                self.asset.quantity += getattr(t, quantity)

            else:
                if t.type == 'Buy':
                    if is_base_asset:
                        self.asset.buy_orders += t.quantity * t.price_usd
                    else:
                        self.asset.buy_orders -= t.quantity2
                else:
                    if is_base_asset:
                        self.asset.sell_orders -= t.quantity

    def get_transaction(self, transaction_id: str | int | None):
        return find_by_attr(self.asset.transactions, 'id', transaction_id)

    def create_transaction(self) -> Transaction:
        """Возвращает новую транзакцию."""
        transaction = Transaction()
        transaction.type = 'TransferOut'
        transaction.ticker_id = self.asset.ticker_id
        transaction.base_ticker = self.asset.ticker
        transaction.date = datetime.now(timezone.utc)
        transaction.wallet_id = self.asset.wallet_id
        transaction.quantity=0

        transaction.wallet_asset = self.asset
        transaction.wallet = self.asset.wallet
        return transaction

    def delete(self) -> None:
        for transaction in self.asset.transactions:
            transaction.service.delete()

        WalletAssetRepository.delete(self.asset)
