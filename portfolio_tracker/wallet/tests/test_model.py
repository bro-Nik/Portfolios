import unittest

from portfolio_tracker.user.models import User
from portfolio_tracker.portfolio.models import Ticker, Transaction
from tests import app, db
from ..models import Wallet, WalletAsset


class TestWalletModel(unittest.TestCase):
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

    def test_edit(self):
        w = Wallet(id=1, name='Test')
        self.user.wallets = [w]

        w.edit({'name': 'Test', 'comment': 'Comment'})
        self.assertEqual(w.name, 'Test2')
        self.assertEqual(w.comment, 'Comment')

    def test_is_empty(self):
        w1 = Wallet(id=1)
        w2 = Wallet(id=2, comment='Comment')
        w3 = Wallet(id=3, transactions=[Transaction()])

        # Пустой кошелек
        self.assertEqual(w1.is_empty(), True)

        # Кошелек с комментарием
        self.assertEqual(w2.is_empty(), False)

        # Кошелек с транзакциями
        self.assertEqual(w3.is_empty(), False)

    def test_update_price(self):
        # Тикеры
        btc = Ticker(id='btc', stable=False, price=26000)
        eth = Ticker(id='eth', stable=False, price=3000)
        usd = Ticker(id='usd', stable=True, price=1)

        # Активы
        a1 = WalletAsset(ticker=btc, quantity=0.5, sell_orders=0, buy_orders=1000)
        a2 = WalletAsset(ticker=eth, quantity=1, sell_orders=0.3, buy_orders=0)
        a3 = WalletAsset(ticker=usd, quantity=3000, buy_orders=1000)

        # Кошельки
        w = Wallet(id=1, wallet_assets=[a1, a2, a3])

        w.update_price()
        self.assertEqual(w.cost_now, 19000)
        self.assertEqual(w.in_orders, 1000)
        self.assertEqual(w.free, 2000)
        self.assertEqual(w.assets, [a1, a2])
        self.assertEqual(w.stable_assets, [a3])

    def test_delete_if_empty(self):
        w = Wallet(id=1)
        self.user.wallets = [w]
        db.session.commit()

        w.delete_if_empty()
        self.assertEqual(self.user.wallets, [])

    def test_delete(self):
        w = Wallet(id=1, comment='Comment')
        self.user.wallets = [w]
        db.session.commit()

        w.delete()
        self.assertEqual(self.user.wallets, [])


class TestWalletAssetModel(unittest.TestCase):
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

    def test_is_empty(self):
        # Активы
        a1 = WalletAsset()
        a2 = WalletAsset(transactions=[])
        a3 = WalletAsset(transactions=[Transaction()])

        # Без транзакций
        self.assertEqual(a1.is_empty(), True)
        self.assertEqual(a2.is_empty(), True)

        # С транзакциями
        self.assertEqual(a3.is_empty(), False)

    def test_update_price(self):
        # Актив
        btc = Ticker(id='btc', stable=False, price=26000)
        a = WalletAsset(ticker=btc, quantity=0.5, sell_orders=0.1, buy_orders=1000)

        a.update_price()

        self.assertEqual(a.cost_now, 13000)
        self.assertEqual(a.free, 0.4)

    def test_delete_if_empty(self):
        # Актив
        a = WalletAsset(ticker_id='btc')
        w = Wallet(id=1, wallet_assets=[a])
        db.session.add(w)
        db.session.commit()

        a.delete_if_empty()
        self.assertEqual(w.wallet_assets, [])

    def test_delete(self):
        # Актив
        a = WalletAsset(ticker_id='btc', transactions=[Transaction()])
        w = Wallet(id=1, wallet_assets=[a])
        db.session.add(w)
        db.session.commit()

        a.delete()
        self.assertEqual(w.wallet_assets, [])
