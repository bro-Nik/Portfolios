import unittest

from portfolio_tracker.app import db
from portfolio_tracker.models import Asset, OtherAsset, OtherBody, Portfolio, \
    Transaction, User
from portfolio_tracker.portfolio.utils import create_new_asset, \
    create_new_portfolio, create_new_transaction, get_asset, get_other_asset, \
    get_other_body, get_portfolio, get_transaction
from tests import app


class TestPortfolioUtils(unittest.TestCase):
    """Класс для тестирования функций портфелей"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        u = User(email='test@test', password='dog')
        db.session.add(u)

        self.u = u
        self.p1 = Portfolio(id=1)
        self.p2 = Portfolio(id=2)
        self.p3 = Portfolio(id=3)

        u.portfolios = [self.p1, self.p2, self.p3]
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_portfolio(self):
        self.assertEqual(get_portfolio(1, self.u), self.p1)
        self.assertEqual(get_portfolio(3, self.u), self.p3)
        self.assertEqual(get_portfolio(4, self.u), None)

    def test_get_asset(self):
        a1 = Asset(ticker_id='btc')
        self.p1.assets.append(a1)
        self.assertEqual(get_asset(self.p1, 'btc'), a1)
        self.assertEqual(get_asset(self.p1, 'btc').portfolio, self.p1)

        a2 = Asset(ticker_id='eth')
        self.p2.assets.append(a2)
        self.assertEqual(get_asset(self.p2, 'eth'), a2)
        self.assertEqual(get_asset(self.p2, 'eth').portfolio, self.p2)

        self.assertEqual(get_asset(self.p3, 'aapl'), None)
        a3 = get_asset(self.p3, 'aapl', create=True)
        self.assertEqual(a3.ticker_id, 'aapl')
        self.assertEqual(get_asset(self.p3, 'aapl').portfolio, self.p3)

    def test_get_other_asset(self):
        a1 = OtherAsset(id=1)
        self.p1.other_assets.append(a1)
        self.assertEqual(get_other_asset(self.p1, 1), a1)
        self.assertEqual(get_other_asset(self.p1, 1).portfolio, self.p1)

        a2 = OtherAsset(id=2)
        self.p2.other_assets.append(a2)
        self.assertEqual(get_other_asset(self.p2, 2), a2)
        self.assertEqual(get_other_asset(self.p2, 2).portfolio, self.p2)

        self.assertEqual(get_other_asset(self.p3, 3), None)

    def test_get_transaction(self):
        t = Transaction(wallet_id=1, portfolio=self.p1)
        a = Asset(ticker_id='btc', transactions=[t,])
        self.p1.assets.append(a)

        db.session.commit()

        self.assertEqual(get_transaction(None, 1), None)
        self.assertEqual(get_transaction(a, 1), t)
        self.assertEqual(get_transaction(a, 2), None)

    def test_get_other_body(self):
        b = OtherBody(id=1)
        a = OtherAsset(id=1, bodies=[b,])
        self.p1.other_assets.append(a)

        db.session.commit()

        self.assertEqual(get_other_body(None, 1), None)
        self.assertEqual(get_other_body(a, 1), b)
        self.assertEqual(get_other_body(a, 2), None)

    def test_create_new_portfolio(self):
        create_new_portfolio({'market': 'crypto'}, self.u)
        self.assertEqual(len(self.u.portfolios), 4)

    def test_create_new_asset(self):
        a = create_new_asset(self.p1, 'btc')
        self.assertEqual(self.p1.assets, [a,])
        self.assertEqual(a.ticker_id, 'btc')

    def test_create_new_transaction(self):
        a = Asset(ticker_id='btc')
        self.p1.assets.append(a)
        db.session.commit()

        t = create_new_transaction(a)
        self.assertEqual(a.transactions, [t,])
