import unittest
from unittest.mock import patch

from portfolio_tracker.wallet.models import Wallet, WalletAsset
from portfolio_tracker.user.models import User
from portfolio_tracker.portfolio.models import Transaction
from tests import app, db


class TestWalletAssetService(unittest.TestCase):
    """Класс для тестирования методов кошелька"""

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Создаем тестовые данные
        self.user = User(id=1, email='1@1', password='')
        self.asset = WalletAsset(ticker_id='btc', quantity=5, buy_orders=100, sell_orders=0)
        self.wallet = Wallet(id=1, user_id=1, name='Test Wallet', assets=[self.asset])
        self.user.wallets.append(self.wallet)
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_set_default_data(self):
        self.asset.service.set_default_data()
        self.assertEqual(self.asset.quantity, 0)
        self.assertEqual(self.asset.buy_orders, 0)
        self.assertEqual(self.asset.sell_orders, 0)

    def test_recalculate_with_non_order_transactions(self):
        transaction1 = Transaction(id=1, type='Buy', ticker_id='btc', quantity=5)
        transaction2 = Transaction(id=2, type='Sell', ticker_id='btc', quantity=-3)
        self.asset.transactions = [transaction1, transaction2]

        self.asset.service.recalculate()
        self.assertEqual(self.asset.quantity, 2)
        self.assertEqual(self.asset.buy_orders, 0)
        self.assertEqual(self.asset.sell_orders, 0)

    def test_recalculate_with_order_transactions(self):
        transaction1 = Transaction(id=1, type='Buy', ticker_id='btc', quantity=5, price_usd=100, order=True)
        transaction2 = Transaction(id=2, type='Sell', ticker_id='btc', quantity=-3, order=True)
        self.asset.transactions = [transaction1, transaction2]

        self.asset.service.recalculate()
        self.assertEqual(self.asset.quantity, 0)
        self.assertEqual(self.asset.buy_orders, 500)
        self.assertEqual(self.asset.sell_orders, 3)

    def test_get_transaction(self):
        transaction = Transaction(id=1, type='Buy', ticker_id='btc', quantity=5)
        self.asset.transactions = [transaction]
        result = self.asset.service.get_transaction(1)
        self.assertEqual(result, transaction)

    def test_create_transaction(self):
        transaction = self.asset.service.create_transaction()
        self.assertEqual(transaction.type, 'TransferOut')
        self.assertEqual(transaction.ticker_id, 'btc')
        self.assertEqual(transaction.wallet_id, 1)
        self.assertEqual(transaction.quantity, 0)

    @patch('portfolio_tracker.wallet.services.asset.WalletAssetRepository.delete')
    @patch('portfolio_tracker.portfolio.services.transaction.TransactionService.delete')
    def test_delete(self, mock_transaction_delete, mock_asset_delete):
        transaction = Transaction(id=1, type='Buy', ticker_id='btc', quantity=5)
        self.asset.transactions = [transaction]
        self.asset.service.delete()

        mock_transaction_delete.assert_called_once()
        mock_asset_delete.assert_called_once_with(self.asset)


if __name__ == '__main__':
    unittest.main(verbosity=2)
