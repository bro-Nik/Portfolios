import unittest
from datetime import datetime

from portfolio_tracker.app import db
from portfolio_tracker.models import Ticker, Transaction, User, Wallet, \
    WalletAsset
from portfolio_tracker.wallet.utils import create_new_transaction, \
    create_new_wallet, create_new_wallet_asset, get_transaction, get_wallet, \
    get_wallet_asset, get_wallet_has_asset, last_wallet, \
    last_wallet_transaction
from tests import app


class TestWalletUtils(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        u = User(email='test@test', password='dog')
        db.session.add(u)

        self.u = u
        self.w1 = Wallet(id=1, name='Test')
        self.w2 = Wallet(id=2, name='Test2')
        self.w3 = Wallet(id=3, name='Test3')

        u.wallets = [self.w1, self.w2, self.w3]
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_wallet(self):
        self.assertEqual(get_wallet(1, self.u), self.w1)
        self.assertEqual(get_wallet(3, self.u), self.w3)
        self.assertEqual(get_wallet(4, self.u), None)

    def test_get_wallet_has_asset(self):
        a1 = WalletAsset(ticker=Ticker(id='btc', stable=True), quantity=10)
        self.w1.wallet_assets.append(a1)

        self.assertEqual(get_wallet_has_asset('btc', self.u), self.w1)
        self.assertEqual(get_wallet_has_asset('eth', self.u), None)

    def test_get_wallet_asset(self):
        a1 = WalletAsset(ticker_id='btc')
        self.w1.wallet_assets.append(a1)
        self.assertEqual(get_wallet_asset(self.w1, 'btc'), a1)

        a2 = WalletAsset(ticker_id='eth')
        self.w2.wallet_assets.append(a2)
        self.assertEqual(get_wallet_asset(self.w2, 'eth'), a2)

        self.assertEqual(get_wallet_asset(self.w3, 'usdt'), None)
        a3 = WalletAsset(ticker_id='usdt')
        self.w3.wallet_assets.append(a3)
        self.assertEqual(get_wallet_asset(self.w3, 'usdt'), a3)

    def test_get_transaction(self):
        t1 = Transaction(id=1, wallet_id=1, ticker_id='btc')
        t2 = Transaction(id=2, wallet_id=2, ticker_id='eth')

        a1 = WalletAsset(ticker_id='btc')
        a2 = WalletAsset(ticker_id='eth')

        self.w1.wallet_assets.append(a1)
        self.w1.transactions.append(t1)

        self.w2.wallet_assets.append(a2)
        self.w2.transactions.append(t2)

        self.assertEqual(get_transaction(a1, 1), t1)
        self.assertEqual(get_transaction(a2, 1), None)
        self.assertEqual(get_transaction(a2, 2), t2)

    def test_last_wallet(self):
        t1 = Transaction(type='Buy', date=datetime(2023, 10, 10))
        t2 = Transaction(type='Buy', date=datetime(2023, 10, 11))
        t3 = Transaction(type='Buy', date=datetime(2023, 10, 9))

        self.w1.transactions.append(t1)
        self.w2.transactions.append(t2)
        self.w3.transactions.append(t3)

        self.assertEqual(last_wallet('Buy', self.u), self.w2)

    def test_last_wallet_transaction(self):
        t1 = Transaction(type='Buy', date=datetime(2023, 10, 10))
        t2 = Transaction(type='Sell', date=datetime(2023, 10, 11))

        self.w1.transactions = [t1, t2]

        self.assertEqual(last_wallet_transaction(self.w1, 'Buy'), t1)
        self.assertEqual(last_wallet_transaction(self.w1, 'Sell'), t2)

    def test_create_new_wallet(self):
        create_new_wallet(self.u)
        self.assertEqual(len(self.u.wallets), 4)

    def test_create_new_wallet_asset(self):
        a = create_new_wallet_asset(self.w1, 'btc')
        self.assertEqual(len(self.w1.wallet_assets), 1)
        self.assertEqual(a.ticker_id, 'btc')

    def test_create_new_transaction(self):
        a = WalletAsset(ticker_id='btc')
        self.w1.wallet_assets.append(a)
        create_new_transaction(a)

        self.assertEqual(len(a.transactions), 1)
