import unittest

from tests import app, db
from portfolio_tracker.portfolio.models import OtherAsset, OtherBody


class TestOtherBodyService(unittest.TestCase):
    """Класс для тестирования методов тела офлайн актива"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Актив портфеля
        self.asset = OtherAsset(id=1, portfolio_id=1)
        db.session.add(self.asset)

        # Тело актива
        self.body = OtherBody(id=1, asset_id=1, name='', amount_ticker_id='', cost_now_ticker_id='')
        db.session.add(self.body)

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit(self):
        form = {'name': 'New Name',
                'amount_ticker_id': 'usdt',
                'cost_now_ticker_id': 'usdt',
                'amount': '1000',
                'cost_now': '1500',
                'comment': 'New Comment'}

        self.body.service.edit(form)

        self.assertEqual(self.body.name, 'New Name')
        self.assertEqual(self.body.amount, 1000)
        self.assertEqual(self.body.amount_ticker_id, 'usdt')
        self.assertEqual(self.body.amount_usd, 0)
        self.assertEqual(self.body.cost_now, 1500)
        self.assertEqual(self.body.cost_now_ticker_id, 'usdt')
        self.assertEqual(self.body.cost_now_usd, 0)
        self.assertEqual(self.body.comment, 'New Comment')

    def test_update_dependencies(self):
        self.body.amount_usd = 1000
        self.body.cost_now_usd = 500
        self.body.asset.amount = 1500
        self.body.asset.cost_now = 500

        # Применить транзакцию
        self.body.service.update_dependencies()
        self.assertEqual(self.body.asset.amount, 2500)
        self.assertEqual(self.body.asset.cost_now, 1000)

        # Отменить
        self.body.service.update_dependencies('cancel')
        self.assertEqual(self.body.asset.amount, 1500)
        self.assertEqual(self.body.asset.cost_now, 500)

    def test_delete(self):
        self.body.amount_usd = 1000
        self.body.cost_now_usd = 500
        self.body.asset.amount = 1500
        self.body.asset.cost_now = 500

        # Удалить
        self.body.service.delete()
        self.assertEqual(self.body.asset.amount, 500)
        self.assertEqual(self.body.asset.cost_now, 0)
        self.assertIsNone(db.session.get(OtherBody, 1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
