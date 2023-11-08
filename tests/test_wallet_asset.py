import unittest

from portfolio_tracker.app import db
from portfolio_tracker.general_functions import get_price
from portfolio_tracker.models import Ticker, Transaction, User, Wallet, WalletAsset
from tests import app


class TestWalletAssetModel(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.u = User(email='test@test', password='dog')
        db.session.add(self.u)

        self.a = WalletAsset(ticker=Ticker(id='btc', stable=None), quantity=10)
        self.w = Wallet(id=1, wallet_assets=[self.a,])

        self.u.wallets = [self.w,]
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_asset_is_empty(self):
        self.assertEqual(self.a.is_empty(), True)

        self.a.transactions = [Transaction(),]
        self.assertEqual(self.a.is_empty(), False)

    def test_asset_update_price(self):
        self.a.update_price()

        self.assertEqual(self.a.price, get_price('btc'))
        self.assertEqual(self.a.cost_now, self.a.price * 10)
        self.assertEqual(self.a.free, 10)

    def test_asset_delete(self):
        self.a.delete()
        self.assertEqual(self.w.wallet_assets, [])
