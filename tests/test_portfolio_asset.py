import unittest

from flask_login import login_user

from tests import app, db
from portfolio_tracker.user.models import User
from portfolio_tracker.watchlist.models import Alert
from portfolio_tracker.portfolio.models import Asset, Portfolio, Ticker, Transaction
from portfolio_tracker.wallet.models import Wallet, WalletAsset


class TestPortfolioAsset(unittest.TestCase):
    """Класс для тестирования методов актива"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.asset = Asset(ticker_id='btc', portfolio_id=1, comment='')
        db.session.add(self.asset)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_is_empty(self):
        self.assertEqual(self.asset.is_empty, True)

    def test_not_empty_with_comment(self):
        self.asset.comment = 'Comment'
        self.assertEqual(self.asset.is_empty, False)

    def test_not_empty_with_transaction(self):
        self.asset.transactions = [Transaction()]
        self.assertEqual(self.asset.is_empty, False)

    def test_price(self):
        self.asset.ticker = Ticker(price=26000)
        self.assertEqual(self.asset.price, 26000)

    def test_cost_now(self):
        self.asset.quantity = 3
        self.asset.ticker = Ticker(price=1000)
        self.assertEqual(self.asset.cost_now, 3000)

    def test_free(self):
        self.asset.quantity = 3
        self.assertEqual(self.asset.free, 3)

        # Влияние ордеров
        self.asset.sell_orders = 0.8
        self.assertEqual(self.asset.free, 3 - 0.8)

    def test_average_buy_price(self):
        self.asset.amount = 100
        self.asset.quantity = 5
        self.assertEqual(self.asset.average_buy_price, 20)

        self.asset.amount = 0
        self.asset.quantity = 5
        self.assertEqual(self.asset.average_buy_price, 0)

        self.asset.amount = 100
        self.asset.quantity = 0
        self.assertEqual(self.asset.average_buy_price, 0)


class TestPortfolioAssetService(unittest.TestCase):
    """Класс для тестирования методов актива"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.user = User(email='test@test', password='dog')
        db.session.add(self.user)

        # Тикеры
        self.btc = Ticker(id='btc', name='Bitcoin', price=26000, symbol='bitcoin', market='crypto')
        db.session.add(self.btc)

        # Портфели
        self.portfolio1 = Portfolio(id=1, market='crypto', name='Name1')
        self.portfolio2 = Portfolio(id=2, market='crypto', name='Name2')
        self.user.portfolios = [self.portfolio1, self.portfolio2]

        # Актив портфеля
        self.asset = Asset(id=1, ticker=self.btc, portfolio_id=1)
        db.session.add(self.asset)

        # Кошелек
        self.wallet = Wallet(id=1, name='Name')
        self.user.wallets = [self.wallet]

        # Актив кошелька
        self.wallet_asset = WalletAsset(id=1, ticker=self.btc, wallet_id=1)
        db.session.add(self.wallet_asset)

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_edit_empty_form(self):
        form = {}
        self.asset.service.edit(form)

        self.assertEqual(self.asset.percent, 0)
        self.assertEqual(self.asset.comment, None)

    def test_edit(self):
        form = {'percent': 50, 'comment': 'New Comment'}
        self.asset.service.edit(form)

        self.assertEqual(self.asset.percent, 50)
        self.assertEqual(self.asset.comment, 'New Comment')

    def test_get_transaction(self):
        transaction1 = Transaction(id=1)
        transaction2 = Transaction(id=2)
        transaction3 = Transaction(id=3)
        self.asset.transactions = [transaction1, transaction2, transaction3]

        self.assertEqual(self.asset.service.get_transaction(1), transaction1)
        self.assertEqual(self.asset.service.get_transaction(2), transaction2)
        self.assertEqual(self.asset.service.get_transaction(3), transaction3)
        self.assertEqual(self.asset.service.get_transaction(5), None)

    def test_create_transaction(self):
        transaction = self.asset.service.create_transaction()

        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.type, 'Buy')
        self.assertEqual(transaction.ticker_id, self.asset.ticker_id)
        self.assertEqual(transaction.base_ticker, self.asset.ticker)
        self.assertEqual(transaction.quantity, 0)
        self.assertEqual(transaction.portfolio_id, self.asset.portfolio_id)
        self.assertEqual(transaction.price, 0)

    def test_set_default_data(self):
        self.asset.service.set_default_data()

        self.assertEqual(self.asset.amount, 0)
        self.assertEqual(self.asset.quantity, 0)
        self.assertEqual(self.asset.sell_orders, 0)
        self.assertEqual(self.asset.buy_orders, 0)

    def test_move_asset_to(self):
        # Портфель не найден
        self.asset.service.move_asset_to(portfolio_id=4)
        self.assertEqual(self.asset.portfolio_id, 1)

        self.asset.service.move_asset_to(portfolio_id=2)
        self.assertEqual(self.asset.portfolio_id, 2)

    def test_recalculate(self):
        other = {'quantity2': 0, 'portfolio_id': 1,
                 'price': 0, 'comment': '', 'wallet_id': 1, 'related_transaction_id': 0}

        t1 = Transaction(id=1, order=False, type='Buy', quantity=0.5, price_usd=150, **other)
        t2 = Transaction(id=2, order=False, type='Sell', quantity=-0.25, price_usd=250, **other)
        t3 = Transaction(id=3, order=True, type='Sell', quantity=-0.3, price_usd=350, **other)
        t4 = Transaction(id=4, order=True, type='Buy', quantity=0.5, price_usd=50, **other)
        self.asset.transactions = [t1, t2, t3, t4]

        self.asset.service.recalculate()

        self.assertEqual(self.asset.quantity, 0.25)
        self.assertEqual(self.asset.average_buy_price, 50)
        self.assertEqual(self.asset.amount, 12.5)
        self.assertEqual(self.asset.buy_orders, 25)
        self.assertEqual(self.asset.sell_orders, 0.3)

    def test_delete(self):
        other = {'quantity': 0, 'quantity2': 0, 'portfolio_id': 1, 'price_usd': 0,
                 'type': 'buy', 
                 'price': 0, 'comment': '', 'wallet_id': 1, 'related_transaction_id': 0}

        t1 = Transaction(id=1, ticker_id='btc', **other)
        t2 = Transaction(id=2, ticker_id='btc', **other)
        t3 = Transaction(id=3, ticker_id='btc', **other)
        self.asset.transactions = [t1, t2, t3]

        alert = Alert(id=1, asset_id=1, watchlist_asset_id=1, price=1,
                      price_usd=1, price_ticker_id='usd', type='up', comment='')
        self.asset.alerts = [alert]
        db.session.commit()

        with app.test_request_context():
            login_user(self.user, False)
            # Не удалять, если не пусто
            self.asset.service.delete_if_empty()
            db.session.commit()

            self.assertEqual(self.asset.transactions, [t1, t2, t3])
            self.assertEqual(self.asset.alerts, [alert])
            self.assertEqual(self.portfolio1.assets, [self.asset])
            self.assertEqual(alert.asset_id, self.asset.id)

            # Удаление транзакций, уведомлений и актива
            self.asset.service.delete()
            db.session.commit()

            self.assertEqual(self.asset.transactions, [])
            self.assertEqual(self.asset.alerts, [alert])
            self.assertEqual(self.portfolio1.assets, [])
            self.assertEqual(alert.asset_id, None)

if __name__ == '__main__':
    unittest.main(verbosity=2)
