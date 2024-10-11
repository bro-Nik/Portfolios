import unittest
from datetime import datetime

from flask_login import login_user

from portfolio_tracker.portfolio.models import Ticker, Transaction
from portfolio_tracker.user.models import User
from tests import app, db
from ..models import Wallet, WalletAsset
from ..utils import create_wallet, create_wallet_asset, \
    get_wallet, get_wallet_asset, get_wallet_has_asset, \
    last_wallet, last_wallet_transaction


class TestWalletUtils(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.user = User(email='test@test', password='dog')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_wallet(self):
        # Кошельки
        w1 = Wallet(id=1, name='Test')
        w2 = Wallet(id=2, name='Test2')
        w3 = Wallet(id=3, name='Test3')
        self.user.wallets = [w1, w2, w3]
        db.session.commit()

        with self.app.test_request_context():
            login_user(self.user)

            self.assertEqual(get_wallet(1), w1)
            self.assertEqual(get_wallet(3), w3)
            self.assertEqual(get_wallet(4), None)

    def test_get_wallet_has_asset(self):
        wa = WalletAsset(ticker=Ticker(id='btc'), quantity=10)
        w1 = Wallet(id=1)
        w2 = Wallet(id=2, wallet_assets=[wa])
        w3 = Wallet(id=3)
        self.user.wallets = [w1, w2, w3]
        db.session.commit()

        with self.app.test_request_context():
            login_user(self.user)

            self.assertEqual(get_wallet_has_asset('btc'), w2)
            self.assertEqual(get_wallet_has_asset('eth'), None)

    def test_get_wallet_asset(self):
        a1 = WalletAsset(id=1, ticker=Ticker(id='btc'))
        a2 = WalletAsset(id=2,ticker=Ticker(id='eth'))
        w1 = Wallet(id=2, wallet_assets=[a1])
        w2 = Wallet(id=3, wallet_assets=[a2])
        self.user.wallets = [w1, w2]
        db.session.commit()

        self.assertEqual(get_wallet_asset(None, w1, 'btc'), a1)
        self.assertEqual(get_wallet_asset(1, w1), a1)
        self.assertEqual(get_wallet_asset('1', w1), a1)
        self.assertEqual(get_wallet_asset(None, w2, 'eth'), a2)
        self.assertEqual(get_wallet_asset(2, w2), a2)
        self.assertEqual(get_wallet_asset('2', w2), a2)
        self.assertEqual(get_wallet_asset(None, w2, 'ltc'), None)
        self.assertEqual(get_wallet_asset(3, w2), None)
        self.assertEqual(get_wallet_asset('3', w2), None)
        self.assertEqual(get_wallet_asset(1, None), None)
        self.assertEqual(get_wallet_asset(None, w1, None), None)

    def test_last_wallet(self):
        w1 = Wallet(id=2)
        w2 = Wallet(id=3)
        w3 = Wallet(id=4)
        self.user.wallets = [w1, w2, w3]
        db.session.commit()

        # Без транзакций
        with self.app.test_request_context():
            login_user(self.user)
            self.assertEqual(last_wallet('Buy'), w3)

        # С транзакциями
        w1.transactions.append(Transaction(type='Buy', date=datetime(2023, 10, 10)))
        w2.transactions.append(Transaction(type='Buy', date=datetime(2023, 10, 11)))
        w3.transactions.append(Transaction(type='Buy', date=datetime(2023, 10, 9)))

        with self.app.test_request_context():
            self.assertEqual(last_wallet('Buy'), w2)

    def test_last_wallet_transaction(self):
        # Кошелек
        w = Wallet()
        self.user.wallets = [w]

        # Транзакции
        t1 = Transaction(type='Buy', date=datetime(2023, 10, 10))
        t2 = Transaction(type='Buy', date=datetime(2022, 10, 10))
        t3 = Transaction(type='Sell', date=datetime(2023, 10, 11))
        t4 = Transaction(type='Sell', date=datetime(2022, 10, 11))
        w.transactions = [t1, t2, t3, t4]
        db.session.commit()

        self.assertEqual(last_wallet_transaction(w, 'Buy'), t1)
        self.assertEqual(last_wallet_transaction(w, 'Sell'), t3)

    def test_create_new_wallet(self):
        self.user.currency_ticker_id = 'rub'

        with self.app.test_request_context():
            login_user(self.user)
            self.user.currency_ticker = Ticker(id='rub')
            w = create_wallet()

        self.assertEqual(len(self.user.wallets), 1)
        self.assertEqual(len(w.wallet_assets), 1)
        self.assertEqual(w.wallet_assets[0].ticker_id, 'rub')

    def test_create_new_wallet_asset(self):
        w = Wallet()
        self.user.wallets = [w]

        btc = Ticker(id='btc', symbol='btc', name='btc', price=30000)
        db.session.add(btc)
        db.session.commit()

        a = create_wallet_asset(w, btc)
        self.assertEqual(w.assets, [a])
        self.assertEqual(a.ticker_id, 'btc')

