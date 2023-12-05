import unittest

from flask import current_app

from portfolio_tracker.app import db
from portfolio_tracker.models import Asset, Portfolio, Ticker, Transaction, User, Wallet, WalletAsset
from tests import app


class TestUser(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.u = User(email='test@test', password='dog')
        db.session.add(self.u)

        self.pa = Asset(ticker_id='btc')
        self.wa1 = WalletAsset(ticker=Ticker(id='btc', market='crypto'))
        self.wa2 = WalletAsset(ticker=Ticker(id='usdt', market='crypto', stable=True))

        self.p = Portfolio(id=1, assets=[self.pa,])
        self.w = Wallet(id=1, wallet_assets=[self.wa1, self.wa2,])

        self.u.portfolios = [self.p,]
        self.u.wallets = [self.w,]

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_update_assets(self):
        db.session.add(Transaction(ticker_id='btc', quantity=0.5,
                                   ticker2_id='usdt', quantity2=13000,
                                   price=26000, price_usd=26000, type='Buy',
                                   wallet_id=1, portfolio_id=1, order=False))

        db.session.add(Transaction(ticker_id='btc', quantity=0.5,
                                   ticker2_id='usdt', quantity2=13000,
                                   price=26000, price_usd=26000, type='Buy',
                                   wallet_id=1, portfolio_id=1, order=True))
        db.session.commit()

        self.u.update_assets()

        self.assertEqual(self.pa.quantity, 0.5)
        self.assertEqual(self.pa.in_orders, 13000)
        self.assertEqual(self.pa.amount, 13000)

        self.assertEqual(self.wa1.quantity, 0.5)
        self.assertEqual(self.wa2.quantity, 13000)
        self.assertEqual(self.wa1.buy_orders, 13000)
        self.assertEqual(self.wa1.sell_orders, 0)

    def test_cleare(self):
        self.u.cleare()

        self.assertEqual(len(self.u.portfolios), 0)
        self.assertEqual(len(self.u.wallets), 0)

    def test_delete(self):
        self.u.delete()

        self.assertEqual(len(self.u.portfolios), 0)
        self.assertEqual(len(self.u.wallets), 0)
        self.assertEqual(db.session.execute(db.select(User)).scalar(), None)

    def test_export_import(self):
        db.session.add(Transaction(ticker_id='btc', quantity=0.5,
                                   ticker2_id='usdt', quantity2=13000,
                                   price=26000, price_usd=26000, type='Buy',
                                   wallet_id=1, portfolio_id=1, order=False))

        db.session.add(Transaction(ticker_id='btc', quantity=0.5,
                                   ticker2_id='usdt', quantity2=13000,
                                   price=26000, price_usd=26000, type='Buy',
                                   wallet_id=1, portfolio_id=1, order=True))
        db.session.commit()

        self.u.update_assets()

        data = self.u.export_data()
        self.u.cleare()

        self.u.import_data(data)

        self.assertEqual(len(self.u.portfolios), 1)
        self.assertEqual(len(self.u.wallets), 1)

        self.assertEqual(self.pa.quantity, 0.5)
        self.assertEqual(self.pa.in_orders, 13000)
        self.assertEqual(self.pa.amount, 13000)

        self.assertEqual(self.wa1.quantity, 0.5)
        self.assertEqual(self.wa2.quantity, 13000)
        self.assertEqual(self.wa1.buy_orders, 13000)
        self.assertEqual(self.wa1.sell_orders, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
