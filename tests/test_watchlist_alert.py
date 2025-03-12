import unittest
from unittest.mock import patch

from portfolio_tracker.portfolio.models import Ticker
from portfolio_tracker.watchlist.models import Alert, WatchlistAsset
from tests import app, db


class TestWalletAssetService(unittest.TestCase):
    """Класс для тестирования методов кошелька"""

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Создаем тестовые данные
        self.asset = WatchlistAsset(id=1, user_id=1, ticker_id='btc', comment='')
        self.alert = Alert(watchlist_asset_id=1, price=20000, price_usd=90,
                           price_ticker_id='', type='', comment='')
        self.usdt = Ticker(id='usdt', name='Tether', price=0.5, symbol='usdt', market='crypto')
        self.btc = Ticker(id='btc', name='Bitcoin', price=55000, symbol='btc', market='crypto')
        db.session.add_all([self.alert, self.usdt, self.btc, self.asset])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    @patch('portfolio_tracker.watchlist.repository.AlertRepository.save')
    def test_edit(self, mock_save):
        form = {'price': '20000', 'price_ticker_id': 'usdt', 'comment': 'New Comment'}
        self.alert.service.edit(form)
        self.assertEqual(self.alert.price, 20000)
        self.assertEqual(self.alert.price_ticker_id, 'usdt')
        self.assertEqual(self.alert.price_usd, 40000)
        self.assertEqual(self.alert.comment, 'New Comment')
        self.assertEqual(self.alert.type, 'down')
        mock_save.assert_called_once_with(self.alert)

    def test_turn_off(self):
        self.alert.status = 'on'
        self.alert.service.turn_off()
        self.assertEqual(self.alert.status, 'off')

    def test_turn_on(self):
        self.alert.status = 'off'
        self.alert.transaction_id = 1
        self.alert.service.turn_on()
        self.assertIsNone(self.alert.transaction_id)
        self.assertEqual(self.alert.status, 'on')

    @patch('portfolio_tracker.watchlist.repository.AlertRepository.delete')
    def test_delete(self, mock_delete):
        self.alert.service.delete()
        mock_delete.assert_called_once_with(self.alert)

    @patch('portfolio_tracker.watchlist.repository.AlertRepository.delete')
    def test_delete_with_transaction(self, mock_delete):
        self.alert.transaction_id = 1
        self.alert.service.delete()
        mock_delete.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
