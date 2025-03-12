import unittest
from unittest.mock import patch

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
        self.asset = WatchlistAsset(user_id=1, ticker_id='btc', comment='')
        db.session.add(self.asset)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    @patch('portfolio_tracker.watchlist.repository.AssetRepository.save')
    def test_edit(self, mock_save):
        form = {'comment': 'New Comment'}
        self.asset.service.edit(form)
        self.assertEqual(self.asset.comment, 'New Comment')
        mock_save.assert_called_once_with(self.asset)

    def test_get_alert(self):
        alert = Alert(id=1)
        self.asset.alerts = [alert]
        result = self.asset.service.get_alert(1)
        self.assertEqual(result, alert)

    def test_create_alert(self):
        alert = self.asset.service.create_alert()
        self.assertIsInstance(alert, Alert)

    @patch('portfolio_tracker.watchlist.repository.AssetRepository.delete')
    def test_delete_if_empty(self, mock_delete):
        self.asset.service.delete_if_empty()
        mock_delete.assert_called_once_with(self.asset)

    @patch('portfolio_tracker.watchlist.repository.AssetRepository.delete')
    def test_delete_if_not_empty(self, mock_delete):
        self.asset.comment = 'asfsadfsdf'
        self.asset.service.delete_if_empty()
        mock_delete.assert_not_called()

    @patch('portfolio_tracker.watchlist.repository.AssetRepository.delete')
    def test_delete(self, mock_delete):
        self.asset.service.delete()
        mock_delete.assert_called_once_with(self.asset)


if __name__ == '__main__':
    unittest.main(verbosity=2)
