import unittest

from flask_login import login_user

from portfolio_tracker.wallet.models import Wallet, WalletAsset
from portfolio_tracker.user.models import User
from tests import app, db
from ..models import Asset, OtherAsset, OtherBody, OtherTransaction, \
    Portfolio, Ticker, Transaction
from ..utils import create_new_asset, create_new_other_body, \
    create_new_other_transaction, create_new_portfolio, get_asset, \
    get_body, get_portfolio, get_ticker, get_transaction, \
    create_new_transaction


class TestPortfolioUtils(unittest.TestCase):
    """Класс для тестирования функций портфелей"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.user = User(id=1, email='test@test', password='dog')
        db.session.add(self.user)
        db.session.commit()

        # Login
        with self.app.test_request_context():
            login_user(self.user)

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_portfolio(self):
        # Портфели
        p1 = Portfolio(id=1)
        p2 = Portfolio(id=2)
        p3 = Portfolio(id=3)
        self.user.portfolios = [p1, p2, p3]
        db.session.commit()

        with self.app.test_request_context():
            self.assertEqual(get_portfolio(1), p1)
            self.assertEqual(get_portfolio('3'), p3)
            self.assertEqual(get_portfolio(4), None)
            self.assertEqual(get_portfolio('not_number'), None)
            self.assertEqual(get_portfolio(None), None)

    def test_get_asset(self):
        # Портфели
        p1 = Portfolio(id=1, market='crypto')
        p2 = Portfolio(id=2, market='stocks')
        p3 = Portfolio(id=3, market='other')
        self.user.portfolios = [p1, p2, p3]
        db.session.commit()

        # Crypto
        a1 = Asset(id=3, ticker_id='btc')
        p1.assets.append(a1)

        self.assertEqual(get_asset(None, p1, 'btc'), a1)
        self.assertEqual(get_asset('3', p1), a1)
        self.assertEqual(get_asset(3, p1), a1)
        self.assertEqual(get_asset(None, p1, 'aapl'), None)
        self.assertEqual(get_asset('4', p1), None)
        self.assertEqual(get_asset(None, p1), None)
        self.assertEqual(get_asset(3, None), None)

        # Stocks
        a2 = Asset(id=4, ticker_id='aapl')
        p2.assets.append(a2)

        self.assertEqual(get_asset(None, p2, 'aapl'), a2)
        self.assertEqual(get_asset('4', p2), a2)
        self.assertEqual(get_asset(4, p2), a2)
        self.assertEqual(get_asset(None, p2, 'btc'), None)
        self.assertEqual(get_asset('3', p2), None)
        self.assertEqual(get_asset(None, p2), None)
        self.assertEqual(get_asset(4, None), None)

        # Other
        a3 = OtherAsset(id=2)
        p3.other_assets.append(a3)

        self.assertEqual(get_asset('2', p3), a3)
        self.assertEqual(get_asset(2, p3), a3)
        self.assertEqual(get_asset(None, p3, 'btc'), None)
        self.assertEqual(get_asset('3', p3), None)
        self.assertEqual(get_asset(None, p3), None)
        self.assertEqual(get_asset(4, None), None)

    def test_get_ticker(self):
        # Тикеры
        t1 = Ticker(id='btc')
        t2 = Ticker(id='eth')
        t3 = Ticker(id='aapl')
        db.session.add_all([t1, t2, t3])
        db.session.commit()

        self.assertEqual(get_ticker('btc'), t1)
        self.assertEqual(get_ticker('eth'), t2)
        self.assertEqual(get_ticker('ltc'), None)

    def test_get_transaction(self):
        # Портфели
        p1 = Portfolio(id=1)
        p2 = Portfolio(id=2)
        p3 = Portfolio(id=3)
        self.user.portfolios = [p1, p2, p3]
        db.session.commit()

        t1 = Transaction(id=1)
        a1 = Asset(ticker_id='btc', transactions=[t1,])
        p1.assets.append(a1)

        t2 = Transaction(id=2)
        a2 = Asset(ticker_id='eth', transactions=[t2,])
        p2.assets.append(a2)

        t3 = OtherTransaction(id=3)
        a3 = OtherAsset(id=1, transactions=[t3,])
        p3.other_assets.append(a3)

        # db.session.commit()

        # Transaction
        self.assertEqual(get_transaction(1, a1), t1)
        self.assertEqual(get_transaction('1', a1), t1)
        self.assertEqual(get_transaction(2, a1), None)
        self.assertEqual(get_transaction(1, None), None)
        self.assertEqual(get_transaction('not_number', a1), None)

        self.assertEqual(get_transaction(2, a2), t2)
        self.assertEqual(get_transaction('2', a2), t2)
        self.assertEqual(get_transaction(1, a2), None)
        self.assertEqual(get_transaction(2, None), None)
        self.assertEqual(get_transaction('not_number', a2), None)

        # Other transaction

        self.assertEqual(get_transaction(3, a3), t3)
        self.assertEqual(get_transaction('3', a3), t3)
        self.assertEqual(get_transaction(1, a3), None)
        self.assertEqual(get_transaction(3, None), None)
        self.assertEqual(get_transaction('not_number', a3), None)
        self.assertEqual(get_transaction(3, a2), None)

    def test_get_body(self):
        b1 = OtherBody(id=1)
        a1 = OtherAsset(id=1, bodies=[b1,])

        b2 = OtherBody(id=2)
        a2 = OtherAsset(id=2, bodies=[b2,])

        db.session.commit()

        self.assertEqual(get_body(1, a1), b1)
        self.assertEqual(get_body('1', a1), b1)
        self.assertEqual(get_body(2, a1), None)
        self.assertEqual(get_body(1, None), None)
        self.assertEqual(get_body('not_number', a1), None)

        self.assertEqual(get_body(2, a2), b2)
        self.assertEqual(get_body('2', a2), b2)
        self.assertEqual(get_body(1, a2), None)
        self.assertEqual(get_body(2, None), None)
        self.assertEqual(get_body('not_number', a2), None)

    def test_create_new_portfolio(self):
        with self.app.test_request_context():
            p = create_new_portfolio()

        self.assertEqual(self.user.portfolios[-1], p)

    def test_create_new_asset(self):
        # Портфели
        p1 = Portfolio(id=1, market='crypto')
        p2 = Portfolio(id=2, market='other')
        self.user.portfolios = [p1, p2]
        db.session.commit()

        # Assets
        a = create_new_asset(p1, Ticker(id='btc'))
        self.assertEqual(p1.assets, [a,])
        self.assertEqual(a.ticker_id, 'btc')

        # Other asset
        oa = create_new_asset(p2)
        self.assertEqual(p2.other_assets, [oa,])


    def test_create_new_transaction(self):
        # Портфель
        p = Portfolio(id=1, market='crypto')
        w = Wallet(id=2)

        a1 = Asset(ticker_id='btc', portfolio_id=1)
        a2 = WalletAsset(ticker_id='usd', wallet_id=2)
        db.session.add_all([p, w, a1, a2])

        db.session.commit()

        # Asset
        self.assertEqual(a1.transactions, [])
        t1 = create_new_transaction(a1)
        self.assertEqual(a1.transactions, [t1,])
        t2 = create_new_transaction(a1)
        self.assertEqual(a1.transactions, [t1, t2])

        # WalletAsset
        self.assertEqual(a2.transactions, [])
        t3 = create_new_transaction(a2)
        self.assertEqual(a2.transactions, [t3,])
        t4 = create_new_transaction(a2)
        self.assertEqual(a2.transactions, [t3, t4])

    def test_create_new_other_transaction(self):
        # Портфель
        p = Portfolio(id=1, market='other')
        a = OtherAsset(id=1, portfolio_id=1)
        db.session.add_all([p, a])
        db.session.commit()

        self.assertEqual(a.transactions, [])
        t1 = create_new_other_transaction(a)
        self.assertEqual(a.transactions, [t1,])
        t2 = create_new_other_transaction(a)
        self.assertEqual(a.transactions, [t1, t2])

    def test_create_new_other_body(self):
        # Портфель
        p = Portfolio(id=1, market='other')
        a = OtherAsset(id=1, portfolio_id=1)
        db.session.add_all([p, a])
        db.session.commit()

        self.assertEqual(a.bodies, [])
        b1 = create_new_other_body(a)
        self.assertEqual(a.bodies, [b1,])
        b2 = create_new_other_body(a)
        self.assertEqual(a.bodies, [b1, b2])
