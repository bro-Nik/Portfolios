import time
from datetime import datetime, timedelta
import unittest

from tests import app, db
from portfolio_tracker.portfolio.models import OtherAsset, OtherTransaction


class TestOtherTransactionService(unittest.TestCase):
    """Класс для тестирования методов транзакции офлайн актива"""

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Актив портфеля
        self.asset = OtherAsset(id=1, portfolio_id=1)
        db.session.add(self.asset)

        # Транзакция
        self.transaction = OtherTransaction(id=1, asset_id=1, amount_ticker_id='', type='')
        db.session.add(self.transaction)

        self.date = datetime.now()
        # self.comment = 'Comment'

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit(self):
        form = {'date': self.date,
                'type': 'Profit',
                'amount_ticker_id': 'usdt',
                'amount': '1000',
                'comment': 'New Comment'}

        self.transaction.service.edit(form)

        self.assertEqual(self.transaction.date, self.date + timedelta(seconds=time.timezone))
        self.assertEqual(self.transaction.type, 'Profit')
        self.assertEqual(self.transaction.amount_ticker_id, 'usdt')
        self.assertEqual(self.transaction.amount, 1000)
        self.assertEqual(self.transaction.amount_usd, 0)
        self.assertEqual(self.transaction.comment, 'New Comment')

    def test_update_dependencies(self):
        self.transaction.amount_usd = 1000
        self.transaction.portfolio_asset.cost_now = 500

        # Применить транзакцию
        self.transaction.service.update_dependencies()
        self.assertEqual(self.transaction.portfolio_asset.cost_now, 1500)

        # Отменить транзакцию
        self.transaction.service.update_dependencies('cancel')
        self.assertEqual(self.transaction.portfolio_asset.cost_now, 500)

    def test_delete(self):
        self.transaction.amount_usd = 1000
        self.transaction.portfolio_asset.cost_now = 1500

        # Удалить транзакцию
        self.transaction.service.delete()
        self.assertEqual(self.transaction.portfolio_asset.cost_now, 500)
        self.assertIsNone(db.session.get(OtherTransaction, 1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
