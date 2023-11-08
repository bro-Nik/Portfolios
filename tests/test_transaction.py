from datetime import datetime
import unittest

from portfolio_tracker.app import db
from portfolio_tracker.general_functions import get_price
from portfolio_tracker.models import Asset, OtherAsset, Portfolio, Transaction, User, Wallet
from portfolio_tracker.portfolio.utils import create_new_portfolio, get_asset, get_portfolio, get_transaction
from tests import app


class TestTransactionModel(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        u = User(email='test@test', password='dog')
        db.session.add(u)

        self.u = u
        self.t1 = Transaction(ticker_id='btc', portfolio_id=1, wallet_id=1)
        self.a = Asset(ticker_id='btc', transactions=[self.t1,])
        self.p = Portfolio(id=1, assets=[self.a,])
        self.w = Wallet(id=1)

        u.portfolios = [self.p,]
        u.wallets = [self.w,]
        db.session.commit()
        self.t1.asset_id = self.a.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_transaction_edit(self):
        t = self.t1
        t.edit({'type': 'Buy', 'date': datetime.utcnow(), 'comment': 'Comment',
                'ticker2_id': 'usdt', 'price': 26000.00, 'buy_wallet_id': 1,
                'order': True, 'quantity': 0.5})

        self.assertEqual(t.type, 'Buy')
        self.assertEqual(t.comment, 'Comment')
        self.assertEqual(t.ticker_id, 'btc')
        self.assertEqual(t.ticker2_id, 'usdt')
        self.assertEqual(t.price, 26000.00)
        self.assertEqual(t.price_usd, 26000.00 * get_price('usdt', 1))
        self.assertEqual(t.wallet_id, 1)
        self.assertEqual(t.order, True)
        self.assertEqual(t.quantity, 0.5)
        self.assertEqual(t.quantity2, -13000.00)
        self.assertEqual(t.alert.id, 1)

    def test_transaction_update_dependencies(self):
        t = self.t1

        # Buy
        t.edit({'type': 'Buy', 'date': datetime.utcnow(), 'comment': 'Comment',
                'ticker2_id': 'usdt', 'price': 26000.00, 'buy_wallet_id': 1,
                'order': False, 'quantity': 0.5})

        t.update_dependencies()
        self.assertEqual(len(self.w.wallet_assets), 2)
        self.assertEqual(self.a.quantity, 0.5)
        self.assertEqual(self.a.amount, 13000)
        self.assertEqual(self.w.wallet_assets[0].quantity, 0.5)
        self.assertEqual(self.w.wallet_assets[1].quantity, -13000)

        t.update_dependencies('cancel')
        self.assertEqual(self.a.quantity, 0)
        self.assertEqual(self.a.amount, 0)
        self.assertEqual(self.w.wallet_assets[0].quantity, 0)
        self.assertEqual(self.w.wallet_assets[1].quantity, 0)

        # Sell
        t.edit({'type': 'Sell', 'date': datetime.utcnow(), 'comment': 'Comment',
                'ticker2_id': 'usdt', 'price': 26000.00, 'sell_wallet_id': 1,
                'order': False, 'quantity': 0.5})

        t.update_dependencies()
        self.assertEqual(self.a.quantity, -0.5)
        self.assertEqual(self.a.amount, -13000)
        self.assertEqual(self.w.wallet_assets[0].quantity, -0.5)
        self.assertEqual(self.w.wallet_assets[1].quantity, 13000)

        t.update_dependencies('cancel')
        self.assertEqual(self.a.quantity, 0)
        self.assertEqual(self.a.amount, 0)
        self.assertEqual(self.w.wallet_assets[0].quantity, 0)
        self.assertEqual(self.w.wallet_assets[1].quantity, 0)

        # Buy Order
        t.edit({'type': 'Buy', 'date': datetime.utcnow(), 'comment': 'Comment',
                'ticker2_id': 'usdt', 'price': 26000.00, 'buy_wallet_id': 1,
                'order': True, 'quantity': 0.5})

        t.update_dependencies()
        self.assertEqual(self.a.in_orders, 13000)
        self.assertEqual(self.w.wallet_assets[0].buy_orders, 13000)
        self.assertEqual(self.w.wallet_assets[1].buy_orders, 13000)

        t.update_dependencies('cancel')
        self.assertEqual(self.a.in_orders, 0)
        self.assertEqual(self.w.wallet_assets[0].buy_orders, 0)
        self.assertEqual(self.w.wallet_assets[1].buy_orders, 0)

        # Sell Order
        t.edit({'type': 'Sell', 'date': datetime.utcnow(), 'comment': '',
                'ticker2_id': 'usdt', 'price': 26000.00, 'sell_wallet_id': 1,
                'order': True, 'quantity': 0.5})

        t.update_dependencies()
        self.assertEqual(self.w.wallet_assets[0].sell_orders, 0.5)

        t.update_dependencies('cancel')
        self.assertEqual(self.w.wallet_assets[0].sell_orders, 0)

        # # Input
        # t.edit({'type': 'Input', 'date': datetime.utcnow(), 'comment': '',
        #         'quantity': 0.5})
        #
        # t.update_dependencies()
        # self.assertEqual(self.w.wallet_assets[0].quantity, 0.5)
        #
        # t.update_dependencies('cancel')
        # self.assertEqual(self.w.wallet_assets[0].quantity, 0)

    def test_convert_order_to_transaction(self):
        t = self.t1

        # Buy Order
        t.edit({'type': 'Buy', 'date': datetime.utcnow(), 'comment': 'Comment',
                'ticker2_id': 'usdt', 'price': 26000.00, 'buy_wallet_id': 1,
                'order': True, 'quantity': 0.5})

        t.update_dependencies()
        t.convert_order_to_transaction()

        self.assertEqual(t.order, False)
        self.assertEqual(t.alert, None)
        self.assertEqual(self.a.quantity, 0.5)
        self.assertEqual(self.a.amount, 13000)
        self.assertEqual(self.w.wallet_assets[0].quantity, 0.5)
        self.assertEqual(self.w.wallet_assets[1].quantity, -13000)

    def test_transaction_delete(self):
        t = self.t1

        # Buy
        t.edit({'type': 'Buy', 'date': datetime.utcnow(), 'comment': 'Comment',
                'ticker2_id': 'usdt', 'price': 26000.00, 'buy_wallet_id': 1,
                'order': False, 'quantity': 0.5})

        t.update_dependencies()
        t.delete()

        self.assertEqual(self.a.quantity, 0)
        self.assertEqual(self.a.amount, 0)
        self.assertEqual(self.w.wallet_assets[0].quantity, 0)
        self.assertEqual(self.w.wallet_assets[1].quantity, 0)
        self.assertEqual(self.a.transactions, [])
