from datetime import datetime
import unittest

from tests import app, db
from portfolio_tracker.portfolio.models import PriceHistory, Ticker


class TestTickerService(unittest.TestCase):
    """Класс для тестирования методов тикера"""

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Тикеры
        self.usdt = Ticker(id='usdt', name='USDT', price=0.9, symbol='Tether', market='crypto')
        db.session.add(self.usdt)

        db.session.commit()

        self.date = datetime.now()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit(self):
        form = {'id': 'usd',
                'symbol': 'USD',
                'name': 'Dollar'}
        self.usdt.service.edit(form)

        self.assertEqual(self.usdt.id, 'usd')
        self.assertEqual(self.usdt.symbol, 'USD')
        self.assertEqual(self.usdt.name, 'Dollar')

    def test_set_price(self):
        # Добавляем исторические данные
        h = PriceHistory(date=self.date, price_usd=0.8)
        self.usdt.history.append(h)

        # Цена после изменений
        self.usdt.service.set_price(self.date, 0.5)
        self.assertEqual(h.price_usd, 0.5)

    def test_delete(self):
        h = PriceHistory(id=1, date=self.date, price_usd=0.8)
        self.usdt.history.append(h)
        db.session.commit()

        # Удаление
        self.usdt.service.delete()
        db.session.commit()

        self.assertEqual(self.usdt.history, [])
        self.assertIsNotNone(self.usdt.history)
        self.assertIsNotNone(self.usdt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
