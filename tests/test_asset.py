import unittest

from portfolio_tracker.app import db
from portfolio_tracker.models import Asset, Portfolio, Transaction, User
from tests import app


class TestAssetModel(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.u = User(email='test@test', password='dog')
        db.session.add(self.u)

        self.a = Asset(ticker_id='btc')
        self.p = Portfolio(id=1, assets=[self.a,])

        self.u.portfolios = [self.p,]
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_asset_edit(self):
        a = self.a

        a.edit({'comment': 'Comment', 'percent': 10})

        self.assertEqual(a.comment, 'Comment')
        self.assertEqual(a.percent, 10)

    def test_asset_is_empty(self):
        a = self.a

        self.assertEqual(a.is_empty(), True)

        a.comment = 'Comment'
        self.assertEqual(a.is_empty(), False)

        a.comment = ''
        a.transactions = [Transaction(),]
        self.assertEqual(a.is_empty(), False)

    def test_asset_get_free(self):
        a = self.a
        a.quantity = 10

        self.assertEqual(a.get_free(), 10)

    def test_asset_update_price(self):
        a = self.a
        a.quantity = 10

        a.update_price()

        self.assertEqual(a.price, a.ticker.price)
        self.assertEqual(a.cost_now, a.price * 10)

    def test_asset_delete(self):
        self.a.delete()

        self.assertEqual(self.p.assets, [])
