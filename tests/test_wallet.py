import unittest
from unittest.mock import patch, MagicMock

from flask_login import login_user

from portfolio_tracker.wallet.models import Wallet, WalletAsset
from portfolio_tracker.user.models import User
from portfolio_tracker.portfolio.models import Ticker, Transaction
from tests import app, db


class TestWallet(unittest.TestCase):
    """Класс для тестирования методов кошелька"""

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_is_empty(self):
        wallet = Wallet(id=1, comment='', transactions=[], assets=[])

        # Пустой
        self.assertTrue(wallet.is_empty)

        # С комментарием
        wallet.comment = 'Comment'
        self.assertFalse(wallet.is_empty)
        wallet.comment = ''
        self.assertTrue(wallet.is_empty)

        # С активом
        wallet.assets = [WalletAsset()]
        self.assertFalse(wallet.is_empty)
        wallet.assets = []
        self.assertTrue(wallet.is_empty)

        # С транзакцией
        wallet.transactions = [Transaction()]
        self.assertFalse(wallet.is_empty)
        wallet.transactions = []
        self.assertTrue(wallet.is_empty)


class MockWalletAsset:
    def __init__(self, id=None, ticker_id=None):
        self.id = id
        self.ticker_id = ticker_id
        self.cost_now = 100
        self.buy_orders = 50
        self.wallet = MagicMock()
        self.service = MagicMock()


class TestWalletService(unittest.TestCase):
    """Класс для тестирования методов кошелька"""

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Создаем тестовые данные
        self.user = User(id=1, email='1@1', password='')
        self.wallet = Wallet(id=1, user_id=1, name='Test Wallet')
        self.user.wallets.append(self.wallet)
        db.session.add(self.user)

        self.btc = Ticker(id='btc', name='Bitcoin', price=26000, symbol='btc', market='crypto')
        self.eth = Ticker(id='eth', name='Ethereum', price=2400, symbol='eth', market='crypto')
        self.ltc = Ticker(id='ltc', name='Litecoin', price=200, symbol='eth', market='crypto')
        db.session.add_all([self.btc, self.eth, self.ltc])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit_empty_form(self):
        form = {}
        self.wallet.service.edit(form)

        self.assertEqual(self.wallet.name, 'Test Wallet')
        self.assertEqual(self.wallet.comment, '')

    def test_edit(self):
        form = {'name': 'New Name', 'comment': 'New Comment'}
        self.wallet.service.edit(form)

        self.assertEqual(self.wallet.name, 'New Name')
        self.assertEqual(self.wallet.comment, 'New Comment')

    def test_edit_duplicate_name(self):
        wallet = Wallet(id=2, user_id=1, name='Wallet')
        self.user.wallets.append(wallet)

        form = {'name': 'Test Wallet'}
        wallet.service.edit(form)

        self.assertEqual(wallet.name, 'Test Wallet2')

    def test_update_price(self):
        # Создаем активы для кошелька
        btc = WalletAsset(id=1, ticker=self.btc, buy_orders=0, quantity=0.1)
        eth = WalletAsset(id=2, ticker=self.eth, buy_orders=100, quantity=1.5)
        self.wallet.assets = [btc, eth]

        self.wallet.service.update_price()
        self.assertEqual(self.wallet.cost_now, 6200)
        self.assertEqual(self.wallet.buy_orders, 100)

    def test_get_asset_by_id(self):
        btc = WalletAsset(id=1)
        self.wallet.assets = [btc]
        result = self.wallet.service.get_asset(1)
        self.assertEqual(result, btc)

    def test_get_asset_by_ticker_id(self):
        btc = WalletAsset(id=1, ticker_id='btc')
        self.wallet.assets = [btc]
        result = self.wallet.service.get_asset('btc')
        self.assertEqual(result, btc)

    @patch('portfolio_tracker.wallet.services.wallet.TickerRepository.get')
    @patch('portfolio_tracker.wallet.services.wallet.WalletAssetRepository.create')
    @patch('portfolio_tracker.wallet.services.wallet.WalletAssetRepository.save')
    def test_create_asset(self, mock_save, mock_create, mock_get):
        mock_get.return_value = MagicMock(id='btc')
        mock_create.return_value = MockWalletAsset(id=1, ticker_id='btc')

        asset = self.wallet.service.create_asset('btc')
        self.assertIsNotNone(asset)
        self.assertEqual(asset.ticker_id, 'btc')
        mock_save.assert_called_once()

    @patch('portfolio_tracker.wallet.services.wallet.flash')
    @patch('portfolio_tracker.wallet.services.wallet.WalletService.delete')
    def test_delete_if_empty(self, mock_delete, mock_flash):
        with app.test_request_context():
            login_user(self.user, False)

            self.wallet.service.delete_if_empty()
            mock_flash.assert_not_called()
            mock_delete.assert_called_once()

    @patch('portfolio_tracker.wallet.services.wallet.flash')
    @patch('portfolio_tracker.wallet.services.wallet.WalletService.delete')
    def test_delete_if_not_empty(self, mock_delete, mock_flash):
        with app.test_request_context():
            login_user(self.user, False)

            asset = WalletAsset(id=1, ticker_id='btc')
            self.wallet.assets = [asset]

            self.wallet.service.delete_if_empty()
            mock_delete.assert_not_called()
            mock_flash.assert_called_once()

    @patch('portfolio_tracker.wallet.services.wallet.WalletRepository.delete')
    def test_delete(self, mock_delete):
        asset = WalletAsset(id=1, ticker_id='btc')
        self.wallet.assets = [asset]
        db.session.commit()

        self.wallet.service.delete()
        mock_delete.assert_called_once_with(self.wallet)


if __name__ == '__main__':
    unittest.main(verbosity=2)
