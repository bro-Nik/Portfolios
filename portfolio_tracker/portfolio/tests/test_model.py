from datetime import datetime, timedelta
import time
import unittest

from flask_login import login_user

from portfolio_tracker.wallet.models import Wallet, WalletAsset
from portfolio_tracker.watchlist.models import Alert
from portfolio_tracker.user.models import User
from tests import app, db
from ..models import Asset, OtherAsset, OtherBody, OtherTransaction, \
    Portfolio, PriceHistory, Ticker, Transaction


class TestTransactionModel(unittest.TestCase):
    """Класс для тестирования методов транзакций"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.u = User(email='test@test', password='dog')
        db.session.add(self.u)

        # Тикеры
        self.ticker1 = Ticker(id='btc', name='Bitcoin', price=26000)
        self.ticker2 = Ticker(id='usdt', name='USDT', price=0.9)
        # ticker3 = Ticker(id='usd', name='USD', price=1)
        db.session.add_all([self.ticker1, self.ticker2])

        # Портфель
        self.p = Portfolio(id=1)
        self.u.portfolios = [self.p]

        # Актив портфеля
        self.a = Asset(id=1, ticker=self.ticker1, portfolio_id=1)
        db.session.add(self.a)

        # Кошелек
        self.w = Wallet(id=1)
        self.u.wallets = [self.w]

        # Транзакция
        self.t = Transaction(id=1, wallet_id=1, portfolio_id=1)
        self.a.transactions = [self.t]

        self.date = datetime.now()
        self.comment = 'Comment'

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit_buy(self):
        # Buy
        form = {'date': self.date,
                'type': 'Buy',
                'buy_wallet_id': '1',
                'ticker2_id': 'usdt',
                'price': 26000,
                'quantity': '0.5',
                'order': False,
                'comment': self.comment}

        self.t.edit(form)

        self.assertEqual(self.t.date, self.date + timedelta(seconds=time.timezone))
        self.assertEqual(self.t.ticker_id, 'btc')
        self.assertEqual(self.t.ticker2_id, 'usdt')
        self.assertEqual(self.t.quantity, 0.5)
        self.assertEqual(self.t.quantity2, -13000)
        self.assertEqual(self.t.price, 26000)
        self.assertEqual(self.t.price_usd, 23400)
        self.assertEqual(self.t.type, 'Buy')
        self.assertEqual(self.t.comment, self.comment)
        self.assertEqual(self.t.wallet_id, 1)
        self.assertEqual(self.t.portfolio_id, 1)
        self.assertEqual(self.t.order, False)
        self.assertEqual(self.t.related_transaction_id, None)

        self.assertEqual(self.t.alert, None)
        self.assertEqual(self.t.base_ticker, self.ticker1)
        self.assertEqual(self.t.quote_ticker, self.ticker2)
        self.assertEqual(self.t.related_transaction, None)

    def test_edit_buy_order(self):
        # Buy ордер

        with app.test_request_context():
            login_user(self.u, False)
            form = {'date': self.date,
                    'type': 'Buy',
                    'buy_wallet_id': '1',
                    'ticker2_id': 'usdt',
                    'price': 25000,
                    'quantity2': '13000',
                    'order': True,
                    'comment': self.comment}
            self.t.edit(form)

            self.assertEqual(self.t.date, self.date + timedelta(seconds=time.timezone))
            self.assertEqual(self.t.ticker_id, 'btc')
            self.assertEqual(self.t.ticker2_id, 'usdt')
            self.assertEqual(self.t.quantity, 0.52)
            self.assertEqual(self.t.quantity2, -13000)
            self.assertEqual(self.t.price, 25000)
            self.assertEqual(self.t.price_usd, 22500)
            self.assertEqual(self.t.type, 'Buy')
            self.assertEqual(self.t.comment, self.comment)
            self.assertEqual(self.t.wallet_id, 1)
            self.assertEqual(self.t.portfolio_id, 1)
            self.assertEqual(self.t.order, True)
            self.assertEqual(self.t.related_transaction_id, None)

            # Уведомления
            self.assertEqual(self.t.alert.price, 25000)
            self.assertEqual(self.t.alert.price_usd, 22500)
            self.assertEqual(self.t.alert.price_ticker_id, 'usdt')
            self.assertEqual(self.t.alert.date, self.date + timedelta(seconds=time.timezone))
            self.assertEqual(self.t.alert.transaction_id, 1)
            self.assertEqual(self.t.alert.asset_id, 1)
            self.assertEqual(self.t.alert.comment, self.comment)
            self.assertEqual(self.t.alert.type, 'down')

    def test_edit_sell(self):
        # Sell
        form = {'date': self.date,
                'type': 'Sell',
                'sell_wallet_id': '1',
                'ticker2_id': 'usdt',
                'price': 26000,
                'quantity': '0.5',
                'order': False,
                'comment': self.comment}

        self.t.edit(form)

        self.assertEqual(self.t.date, self.date + timedelta(seconds=time.timezone))
        self.assertEqual(self.t.ticker_id, 'btc')
        self.assertEqual(self.t.ticker2_id, 'usdt')
        self.assertEqual(self.t.quantity, -0.5)
        self.assertEqual(self.t.quantity2, 13000)
        self.assertEqual(self.t.price, 26000)
        self.assertEqual(self.t.price_usd, 23400)
        self.assertEqual(self.t.type, 'Sell')
        self.assertEqual(self.t.comment, self.comment)
        self.assertEqual(self.t.wallet_id, 1)
        self.assertEqual(self.t.portfolio_id, 1)
        self.assertEqual(self.t.order, False)
        self.assertEqual(self.t.related_transaction_id, None)

    def test_edit_sell_order(self):
        # Sell ордер
        form = {'date': self.date,
                'type': 'Sell',
                'sell_wallet_id': '1',
                'ticker2_id': 'usdt',
                'price': 50000,
                'quantity2': '26000',
                'order': True,
                'comment': self.comment}

        with app.test_request_context():
            login_user(self.u, False)
            self.t.edit(form)

            self.assertEqual(self.t.date, self.date + timedelta(seconds=time.timezone))
            self.assertEqual(self.t.ticker_id, 'btc')
            self.assertEqual(self.t.ticker2_id, 'usdt')
            self.assertEqual(self.t.quantity, -0.52)
            self.assertEqual(self.t.quantity2, 26000)
            self.assertEqual(self.t.price, 50000)
            self.assertEqual(self.t.price_usd, 45000)
            self.assertEqual(self.t.type, 'Sell')
            self.assertEqual(self.t.comment, self.comment)
            self.assertEqual(self.t.wallet_id, 1)
            self.assertEqual(self.t.portfolio_id, 1)
            self.assertEqual(self.t.order, True)
            self.assertEqual(self.t.related_transaction_id, None)

            # Уведомления
            self.assertEqual(self.t.alert.price, 50000)
            self.assertEqual(self.t.alert.price_usd, 45000)
            self.assertEqual(self.t.alert.price_ticker_id, 'usdt')
            self.assertEqual(self.t.alert.date, self.date + timedelta(seconds=time.timezone))
            self.assertEqual(self.t.alert.transaction_id, 1)
            self.assertEqual(self.t.alert.asset_id, 1)
            self.assertEqual(self.t.alert.comment, self.comment)
            self.assertEqual(self.t.alert.type, 'up')

    def test_edit_input(self):
        # Input
        form = {'date': self.date,
                'quantity': '0.5',
                'type': 'Input'}

        self.t.edit(form)

        self.assertEqual(self.t.date, self.date + timedelta(seconds=time.timezone))
        self.assertEqual(self.t.ticker_id, 'btc')
        self.assertEqual(self.t.ticker2_id, None)
        self.assertEqual(self.t.quantity, 0.5)
        self.assertEqual(self.t.quantity2, None)
        self.assertEqual(self.t.price, None)
        self.assertEqual(self.t.price_usd, None)
        self.assertEqual(self.t.type, 'Input')
        self.assertEqual(self.t.comment, None)
        self.assertEqual(self.t.wallet_id, 1)
        self.assertEqual(self.t.portfolio_id, 1)
        self.assertEqual(self.t.order, None)
        self.assertEqual(self.t.related_transaction_id, None)

    def test_edit_output(self):
        # Output
        form = {'date': self.date,
                'quantity': '0.5',
                'type': 'Output'}

        self.t.edit(form)

        self.assertEqual(self.t.date, self.date + timedelta(seconds=time.timezone))
        self.assertEqual(self.t.ticker_id, 'btc')
        self.assertEqual(self.t.ticker2_id, None)
        self.assertEqual(self.t.quantity, -0.5)
        self.assertEqual(self.t.quantity2, None)
        self.assertEqual(self.t.price, None)
        self.assertEqual(self.t.price_usd, None)
        self.assertEqual(self.t.type, 'Output')
        self.assertEqual(self.t.comment, None)
        self.assertEqual(self.t.wallet_id, 1)
        self.assertEqual(self.t.portfolio_id, 1)
        self.assertEqual(self.t.order, None)
        self.assertEqual(self.t.related_transaction_id, None)

    def test_edit_transfer_in(self):
        # TransferIn
        form = {'date': self.date,
                'quantity': '0.5',
                'type': 'TransferIn'}

        self.t.edit(form)

        self.assertEqual(self.t.date, self.date + timedelta(seconds=time.timezone))
        self.assertEqual(self.t.ticker_id, 'btc')
        self.assertEqual(self.t.ticker2_id, None)
        self.assertEqual(self.t.quantity, 0.5)
        self.assertEqual(self.t.quantity2, None)
        self.assertEqual(self.t.price, None)
        self.assertEqual(self.t.price_usd, None)
        self.assertEqual(self.t.type, 'TransferIn')
        self.assertEqual(self.t.comment, None)
        self.assertEqual(self.t.wallet_id, 1)
        self.assertEqual(self.t.portfolio_id, 1)
        self.assertEqual(self.t.order, None)
        self.assertEqual(self.t.related_transaction_id, None)

    def test_edit_transfer_out(self):
        # TransferOut
        form = {'date': self.date,
                'quantity': '0.5',
                'type': 'TransferOut'}

        self.t.edit(form)

        self.assertEqual(self.t.date, self.date + timedelta(seconds=time.timezone))
        self.assertEqual(self.t.ticker_id, 'btc')
        self.assertEqual(self.t.ticker2_id, None)
        self.assertEqual(self.t.quantity, -0.5)
        self.assertEqual(self.t.quantity2, None)
        self.assertEqual(self.t.price, None)
        self.assertEqual(self.t.price_usd, None)
        self.assertEqual(self.t.type, 'TransferOut')
        self.assertEqual(self.t.comment, None)
        self.assertEqual(self.t.wallet_id, 1)
        self.assertEqual(self.t.portfolio_id, 1)
        self.assertEqual(self.t.order, None)
        self.assertEqual(self.t.related_transaction_id, None)

    def test_update_dependencies_create_wallet_assets(self):
        # Wallet assets
        self.w.wallet_assets = [WalletAsset(ticker_id='usdt'),
                                WalletAsset(ticker_id='btc')]

        self.t.type = 'Buy'
        self.t.ticker_id = 'btc'
        self.t.ticker2_id = 'usdt'
        self.t.quantity = 0.5
        self.t.quantity2 = -13000
        self.t.price = 26000
        self.t.price_usd = 23400
        self.t.order = False

        db.session.commit()

        self.t.update_dependencies()

        base_asset = None
        for asset in self.t.wallet.wallet_assets:
            if asset.ticker_id == 'btc':
                base_asset = asset
                break

        quote_asset = None
        for asset in self.t.wallet.wallet_assets:
            if asset.ticker_id == 'usdt':
                quote_asset = asset
                break


        self.assertEqual(base_asset.quantity, 0.5)
        self.assertEqual(quote_asset.quantity, -13000)

        # Cancel
        self.t.update_dependencies('cancel')

        self.assertEqual(base_asset.quantity, 0)
        self.assertEqual(quote_asset.quantity, 0)

    def test_update_dependencies_buy(self):
        # Buy
        # Начальные вводные
        self.t.portfolio_asset.amount = 5000
        self.t.portfolio_asset.quantity = 0.3
        self.t.portfolio_asset.in_orders = 500

        base_asset = WalletAsset(id=1, ticker=self.ticker1, wallet_id=1)
        quote_asset = WalletAsset(id=2, ticker=self.ticker2, wallet_id=1)
        db.session.add_all([base_asset, quote_asset])

        base_asset.quantity = 0.5
        quote_asset.quantity = 20000
        base_asset.buy_orders = 300
        base_asset.sell_orders = 0.5
        quote_asset.buy_orders = 1000

        # Вводные транзакции
        self.t.type = 'Buy'
        self.t.ticker_id = 'btc'
        self.t.ticker2_id = 'usdt'
        self.t.quantity = 0.5
        self.t.quantity2 = -13000
        self.t.price = 26000
        self.t.price_usd = 23400
        self.t.order = False

        db.session.commit()

        # Применить транзакцию
        self.t.update_dependencies()

        self.assertEqual(self.t.portfolio_asset.amount, 16700)
        self.assertEqual(self.t.portfolio_asset.quantity, 0.8)
        self.assertEqual(self.t.portfolio_asset.in_orders, 500)
        self.assertEqual(base_asset.quantity, 1)
        self.assertEqual(quote_asset.quantity, 7000)
        self.assertEqual(base_asset.buy_orders, 300)
        self.assertEqual(base_asset.sell_orders, 0.5)
        self.assertEqual(quote_asset.buy_orders, 1000)

        # Отменить транзакцию
        self.t.update_dependencies('cancel')

        self.assertEqual(self.t.portfolio_asset.amount, 5000)
        self.assertEqual(self.t.portfolio_asset.quantity, 0.8-0.5)
        self.assertEqual(self.t.portfolio_asset.in_orders, 500)
        self.assertEqual(base_asset.quantity, 0.5)
        self.assertEqual(quote_asset.quantity, 20000)
        self.assertEqual(base_asset.buy_orders, 300)
        self.assertEqual(base_asset.sell_orders, 0.5)
        self.assertEqual(quote_asset.buy_orders, 1000)

    def test_update_dependencies_buy_order(self):
        # Buy order
        # Начальные вводные
        self.t.portfolio_asset.amount = 5000
        self.t.portfolio_asset.quantity = 0.3
        self.t.portfolio_asset.in_orders = 500

        base_asset = WalletAsset(id=1, ticker=self.ticker1, wallet_id=1)
        quote_asset = WalletAsset(id=2, ticker=self.ticker2, wallet_id=1)
        db.session.add_all([base_asset, quote_asset])

        base_asset.quantity = 0.5
        quote_asset.quantity = 20000
        base_asset.buy_orders = 300
        base_asset.sell_orders = 0.5
        quote_asset.buy_orders = 1000

        # Вводные транзакции
        self.t.type = 'Buy'
        self.t.ticker_id = 'btc'
        self.t.ticker2_id = 'usdt'
        self.t.quantity = 0.5
        self.t.quantity2 = -13000
        self.t.price = 26000
        self.t.price_usd = 23400
        self.t.order = True

        db.session.commit()

        # Применить транзакцию
        self.t.update_dependencies()

        self.assertEqual(self.t.portfolio_asset.amount, 5000)
        self.assertEqual(self.t.portfolio_asset.quantity, 0.3)
        self.assertEqual(self.t.portfolio_asset.in_orders, 12200)
        self.assertEqual(base_asset.quantity, 0.5)
        self.assertEqual(quote_asset.quantity, 20000)
        self.assertEqual(base_asset.buy_orders, 12000)
        self.assertEqual(base_asset.sell_orders, 0.5)
        self.assertEqual(quote_asset.buy_orders, 14000)

        # Отменить транзакцию
        self.t.update_dependencies('cancel')

        self.assertEqual(self.t.portfolio_asset.amount, 5000)
        self.assertEqual(self.t.portfolio_asset.quantity, 0.3)
        self.assertEqual(self.t.portfolio_asset.in_orders, 500)
        self.assertEqual(base_asset.quantity, 0.5)
        self.assertEqual(quote_asset.quantity, 20000)
        self.assertEqual(base_asset.buy_orders, 300)
        self.assertEqual(base_asset.sell_orders, 0.5)
        self.assertEqual(quote_asset.buy_orders, 1000)

    def test_update_dependencies_sell(self):
        # Sell
        # Начальные вводные
        self.t.portfolio_asset.amount = 15000
        self.t.portfolio_asset.quantity = 0.8
        self.t.portfolio_asset.in_orders = 500

        base_asset = WalletAsset(id=1, ticker=self.ticker1, wallet_id=1)
        quote_asset = WalletAsset(id=2, ticker=self.ticker2, wallet_id=1)
        db.session.add_all([base_asset, quote_asset])

        base_asset.quantity = 0.5
        quote_asset.quantity = 20000
        base_asset.buy_orders = 300
        base_asset.sell_orders = 0.5
        quote_asset.buy_orders = 1000

        # Вводные транзакции
        self.t.type = 'Sell'
        self.t.ticker_id = 'btc'
        self.t.ticker2_id = 'usdt'
        self.t.quantity = -0.5
        self.t.quantity2 = 13000
        self.t.price = 26000
        self.t.price_usd = 23400
        self.t.order = False

        db.session.commit()

        # Применить транзакцию
        self.t.update_dependencies()

        self.assertEqual(self.t.portfolio_asset.amount, 3300)
        self.assertEqual(self.t.portfolio_asset.quantity, 0.8-0.5)
        self.assertEqual(self.t.portfolio_asset.in_orders, 500)
        self.assertEqual(base_asset.quantity, 0)
        self.assertEqual(quote_asset.quantity, 33000)
        self.assertEqual(base_asset.buy_orders, 300)
        self.assertEqual(base_asset.sell_orders, 0.5)
        self.assertEqual(quote_asset.buy_orders, 1000)

        # Отменить транзакцию
        self.t.update_dependencies('cancel')

        self.assertEqual(self.t.portfolio_asset.amount, 15000)
        self.assertEqual(self.t.portfolio_asset.quantity, 0.8)
        self.assertEqual(self.t.portfolio_asset.in_orders, 500)
        self.assertEqual(base_asset.quantity, 0.5)
        self.assertEqual(quote_asset.quantity, 20000)
        self.assertEqual(base_asset.buy_orders, 300)
        self.assertEqual(base_asset.sell_orders, 0.5)
        self.assertEqual(quote_asset.buy_orders, 1000)

    def test_update_dependencies_sell_order(self):
        # Sell order
        # Начальные вводные
        self.t.portfolio_asset.amount = 15000
        self.t.portfolio_asset.quantity = 0.8
        self.t.portfolio_asset.in_orders = 500

        base_asset = WalletAsset(id=1, ticker=self.ticker1, wallet_id=1)
        quote_asset = WalletAsset(id=2, ticker=self.ticker2, wallet_id=1)
        db.session.add_all([base_asset, quote_asset])

        base_asset.quantity = 0.5
        quote_asset.quantity = 20000
        base_asset.buy_orders = 300
        base_asset.sell_orders = 0.5
        quote_asset.buy_orders = 1000

        # Вводные транзакции
        self.t.type = 'Sell'
        self.t.ticker_id = 'btc'
        self.t.ticker2_id = 'usdt'
        self.t.quantity = -0.5
        self.t.quantity2 = 13000
        self.t.price = 26000
        self.t.price_usd = 23400
        self.t.order = True

        db.session.commit()

        # Применить транзакцию
        self.t.update_dependencies()

        self.assertEqual(self.t.portfolio_asset.amount, 15000)
        self.assertEqual(self.t.portfolio_asset.quantity, 0.8)
        self.assertEqual(self.t.portfolio_asset.in_orders, 500)
        self.assertEqual(base_asset.quantity, 0.5)
        self.assertEqual(quote_asset.quantity, 20000)
        self.assertEqual(base_asset.buy_orders, 300)
        self.assertEqual(base_asset.sell_orders, 1)
        self.assertEqual(quote_asset.buy_orders, 1000)

        # Отменить транзакцию
        self.t.update_dependencies('cancel')

        self.assertEqual(self.t.portfolio_asset.amount, 15000)
        self.assertEqual(self.t.portfolio_asset.quantity, 0.8)
        self.assertEqual(self.t.portfolio_asset.in_orders, 500)
        self.assertEqual(base_asset.quantity, 0.5)
        self.assertEqual(quote_asset.quantity, 20000)
        self.assertEqual(base_asset.buy_orders, 300)
        self.assertEqual(base_asset.sell_orders, 0.5)
        self.assertEqual(quote_asset.buy_orders, 1000)

    def test_update_dependencies_input(self):
        # Input
        # Начальные вводные
        wallet_asset = WalletAsset(id=2, ticker=self.ticker2, wallet_id=1)
        db.session.add(wallet_asset)

        wallet_asset.quantity = 1000
        wallet_asset.buy_orders = 300
        wallet_asset.sell_orders = 500

        # Вводные транзакции
        self.t.type = 'Input'
        self.t.ticker_id = 'usdt'
        self.t.quantity = 5000

        db.session.commit()

        # Применить транзакцию
        self.t.update_dependencies()

        self.assertEqual(self.t.wallet_asset, wallet_asset)
        self.assertEqual(self.t.wallet_asset.quantity, 6000)
        self.assertEqual(self.t.wallet_asset.buy_orders, 300)
        self.assertEqual(self.t.wallet_asset.sell_orders, 500)

        # Отменить транзакцию
        self.t.update_dependencies('cancel')

        self.assertEqual(self.t.wallet_asset, wallet_asset)
        self.assertEqual(self.t.wallet_asset.quantity, 1000)
        self.assertEqual(self.t.wallet_asset.buy_orders, 300)
        self.assertEqual(self.t.wallet_asset.sell_orders, 500)

    def test_update_dependencies_output(self):
        # Output
        # Начальные вводные
        wallet_asset = WalletAsset(id=2, ticker=self.ticker2, wallet_id=1)
        db.session.add(wallet_asset)

        wallet_asset.quantity = 5000
        wallet_asset.buy_orders = 300
        wallet_asset.sell_orders = 500

        # Вводные транзакции
        self.t.type = 'Output'
        self.t.ticker_id = 'usdt'
        self.t.quantity = -3000

        db.session.commit()

        # Применить транзакцию
        self.t.update_dependencies()

        self.assertEqual(self.t.wallet_asset, wallet_asset)
        self.assertEqual(self.t.wallet_asset.quantity, 2000)
        self.assertEqual(self.t.wallet_asset.buy_orders, 300)
        self.assertEqual(self.t.wallet_asset.sell_orders, 500)

        # Отменить транзакцию
        self.t.update_dependencies('cancel')

        self.assertEqual(self.t.wallet_asset, wallet_asset)
        self.assertEqual(self.t.wallet_asset.quantity, 5000)
        self.assertEqual(self.t.wallet_asset.buy_orders, 300)
        self.assertEqual(self.t.wallet_asset.sell_orders, 500)

    def test_update_dependencies_transfer_in(self):
        # TransferIn
        # Начальные вводные
        wallet_asset = WalletAsset(id=2, ticker=self.ticker2, wallet_id=1)
        db.session.add(wallet_asset)

        wallet_asset.quantity = 5000
        wallet_asset.buy_orders = 300
        wallet_asset.sell_orders = 500

        # Вводные транзакции
        self.t.type = 'TransferIn'
        self.t.ticker_id = 'usdt'
        self.t.quantity = 3000

        db.session.commit()

        # Применить транзакцию
        self.t.update_dependencies()

        self.assertEqual(self.t.wallet_asset, wallet_asset)
        self.assertEqual(self.t.wallet_asset.quantity, 8000)
        self.assertEqual(self.t.wallet_asset.buy_orders, 300)
        self.assertEqual(self.t.wallet_asset.sell_orders, 500)

        # Отменить транзакцию
        self.t.update_dependencies('cancel')

        self.assertEqual(self.t.wallet_asset, wallet_asset)
        self.assertEqual(self.t.wallet_asset.quantity, 5000)
        self.assertEqual(self.t.wallet_asset.buy_orders, 300)
        self.assertEqual(self.t.wallet_asset.sell_orders, 500)

    def test_update_dependencies_transfer_out(self):
        # TransferOut
        # Начальные вводные
        wallet_asset = WalletAsset(id=2, ticker=self.ticker2, wallet_id=1)
        db.session.add(wallet_asset)

        wallet_asset.quantity = 5000
        wallet_asset.buy_orders = 300
        wallet_asset.sell_orders = 500

        # Вводные транзакции
        self.t.type = 'TransferOut'
        self.t.ticker_id = 'usdt'
        self.t.quantity = -3000

        db.session.commit()

        # Применить транзакцию
        self.t.update_dependencies()

        self.assertEqual(self.t.wallet_asset, wallet_asset)
        self.assertEqual(self.t.wallet_asset.quantity, 2000)
        self.assertEqual(self.t.wallet_asset.buy_orders, 300)
        self.assertEqual(self.t.wallet_asset.sell_orders, 500)

        # Отменить транзакцию
        self.t.update_dependencies('cancel')

        self.assertEqual(self.t.wallet_asset, wallet_asset)
        self.assertEqual(self.t.wallet_asset.quantity, 5000)
        self.assertEqual(self.t.wallet_asset.buy_orders, 300)
        self.assertEqual(self.t.wallet_asset.sell_orders, 500)

    def test_convert_order_to_transaction(self):
        # Convert order to transaction
        # Начальные вводные
        self.t.portfolio_asset.amount = 5000
        self.t.portfolio_asset.quantity = 0.3
        self.t.portfolio_asset.in_orders = 15000
        self.t.alert = Alert()

        base_asset = WalletAsset(id=1, ticker=self.ticker1, wallet_id=1)
        quote_asset = WalletAsset(id=2, ticker=self.ticker2, wallet_id=1)
        db.session.add_all([base_asset, quote_asset])

        base_asset.quantity = 0.5
        quote_asset.quantity = 20000
        base_asset.buy_orders = 16000
        base_asset.sell_orders = 0.5
        quote_asset.buy_orders = 17000

        # Вводные транзакции
        self.t.type = 'Buy'
        self.t.ticker_id = 'btc'
        self.t.ticker2_id = 'usdt'
        self.t.quantity = 0.5
        self.t.quantity2 = -13000
        self.t.price = 26000
        self.t.price_usd = 23400
        self.t.order = True

        db.session.commit()

        # Конвертировать транзакцию
        self.t.convert_order_to_transaction()

        self.assertEqual(self.t.portfolio_asset.amount, 16700)
        self.assertEqual(self.t.portfolio_asset.quantity, 0.8)
        self.assertEqual(self.t.portfolio_asset.in_orders, 3300)
        self.assertEqual(self.t.alert, None)
        self.assertEqual(base_asset.quantity, 1)
        self.assertEqual(quote_asset.quantity, 7000)
        self.assertEqual(base_asset.buy_orders, 4300)
        self.assertEqual(base_asset.sell_orders, 0.5)
        self.assertEqual(quote_asset.buy_orders, 4000)

    def test_delete(self):
        # Delete transaction
        # Начальные вводные
        self.t.portfolio_asset.amount = 15000
        self.t.portfolio_asset.quantity = 0.8
        self.t.portfolio_asset.in_orders = 15000
        self.t.alert = Alert()

        portfolio_asset = self.t.portfolio_asset
        alert = self.t.alert

        base_asset = WalletAsset(id=1, ticker=self.ticker1, wallet_id=1)
        quote_asset = WalletAsset(id=2, ticker=self.ticker2, wallet_id=1)
        db.session.add_all([base_asset, quote_asset])

        base_asset.quantity = 1
        quote_asset.quantity = 20000
        base_asset.buy_orders = 16000
        base_asset.sell_orders = 0.5
        quote_asset.buy_orders = 17000

        # Вводные транзакции
        self.t.type = 'Buy'
        self.t.ticker_id = 'btc'
        self.t.ticker2_id = 'usdt'
        self.t.quantity = 0.5
        self.t.quantity2 = -13000
        self.t.price = 26000
        self.t.price_usd = 23400
        self.t.order = False

        db.session.commit()

        # Конвертировать транзакцию
        self.t.delete()

        self.assertEqual(portfolio_asset.amount, 3300)
        self.assertEqual(portfolio_asset.quantity, 0.8 - 0.5)
        self.assertEqual(portfolio_asset.in_orders, 15000)
        self.assertEqual(base_asset.quantity, 0.5)
        self.assertEqual(quote_asset.quantity, 33000)
        self.assertEqual(base_asset.buy_orders, 16000)
        self.assertEqual(base_asset.sell_orders, 0.5)
        self.assertEqual(quote_asset.buy_orders, 17000)


class TestAssetModel(unittest.TestCase):
    """Класс для тестирования методов актива"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.u = User(email='test@test', password='dog')
        db.session.add(self.u)

        # Тикеры
        self.ticker1 = Ticker(id='btc', name='Bitcoin', price=26000)
        db.session.add(self.ticker1)

        # Портфель
        self.p = Portfolio(id=1)
        self.u.portfolios = [self.p]

        # Актив портфеля
        self.a = Asset(id=1, ticker=self.ticker1, portfolio_id=1)
        db.session.add(self.a)

        self.comment = 'Comment'

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit(self):
        # Без данных
        form = {}

        self.a.edit(form)

        self.assertEqual(self.a.percent, 0)
        self.assertEqual(self.a.comment, None)

        # С данными
        form = {'percent': 10,
                'comment': self.comment}

        self.a.edit(form)

        self.assertEqual(self.a.percent, 10)
        self.assertEqual(self.a.comment, self.comment)

    def test_is_empty(self):
        # Пустой актив
        self.assertEqual(self.a.is_empty(), True)

        # Актив с комментарием
        self.a.comment = 'Comment'
        self.assertEqual(self.a.is_empty(), False)
        self.a.comment = ''
        self.assertEqual(self.a.is_empty(), True)

        # Актив с транзакцией
        t = Transaction(id=1, wallet_id=1, portfolio_id=1)
        self.a.transactions = [t]
        self.assertEqual(self.a.is_empty(), False)

    def test_free(self):
        t1 = Transaction(id=1, order=True, type='Buy', quantity=0.5)
        t2 = Transaction(id=2, order=True, type='Sell', quantity=-0.5)
        t3 = Transaction(id=3, order=True, type='Sell', quantity=-0.3)
        self.a.transactions = [t1, t2, t3]
        self.a.quantity = 3

        self.assertEqual(self.a.free, 3 - 0.8)

    def test_update_price(self):
        self.a.quantity = 1.5
        self.a.update_price()

        self.assertEqual(self.a.price, 26000)
        self.assertEqual(self.a.cost_now, 39000)

    def test_delete(self):
        t1 = Transaction(id=1, ticker_id='btc', portfolio_id=1)
        t2 = Transaction(id=2, ticker_id='btc', portfolio_id=1)
        t3 = Transaction(id=3, ticker_id='btc', portfolio_id=1)
        self.a.transactions = [t1, t2, t3]

        alert = Alert(id=1, asset_id=1)
        self.a.alerts = [alert]
        db.session.commit()

        # Удаление транзакций, уведомлений и актива
        with app.test_request_context():
            login_user(self.u, False)
            self.a.delete()
            db.session.commit()

            self.assertEqual(self.a.transactions, [])
            self.assertEqual(self.a.alerts, [])
            self.assertEqual(self.p.assets, [])
            self.assertEqual(alert.asset_id, None)


class TestOtherAssetModel(unittest.TestCase):
    """Класс для тестирования методов офлайн актива"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.u = User(email='test@test', password='dog')
        db.session.add(self.u)

        # Тикеры
        self.ticker = Ticker(id='usdt', name='USDT', price=0.9)
        db.session.add(self.ticker)

        # Портфель
        self.p = Portfolio(id=1)
        self.u.portfolios = [self.p]

        # Актив портфеля
        self.a = OtherAsset(id=1, portfolio_id=1)
        db.session.add(self.a)

        self.date = datetime.now()
        self.comment = 'Comment'

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit(self):
        # Без данных
        form = {}

        self.a.edit(form)

        self.assertEqual(self.a.name, None)
        self.assertEqual(self.a.percent, 0)
        self.assertEqual(self.a.comment, '')

        # С данными
        self.a.name = 'Name'
        db.session.commit()

        form = {'name': 'Name',
                'percent': 10,
                'comment': self.comment}

        self.a.edit(form)

        self.assertEqual(self.a.name, 'Name2')
        self.assertEqual(self.a.percent, 10)
        self.assertEqual(self.a.comment, self.comment)

    def test_is_empty(self):
        # Пустой актив
        self.assertEqual(self.a.is_empty(), True)

        # Актив с комментарием
        self.a.comment = 'Comment'
        self.assertEqual(self.a.is_empty(), False)
        self.a.comment = ''
        self.assertEqual(self.a.is_empty(), True)

        # Актив с транзакцией
        self.a.transactions = [OtherTransaction(id=1)]
        self.assertEqual(self.a.is_empty(), False)
        self.a.transactions = []
        self.assertEqual(self.a.is_empty(), True)

        # Актив с телом актива
        self.a.bodies = [OtherBody(id=1)]
        self.assertEqual(self.a.is_empty(), False)
        self.a.bodies = []
        self.assertEqual(self.a.is_empty(), True)

    def test_delete(self):
        t1 = OtherTransaction(asset_id=1)
        t2 = OtherTransaction(asset_id=1)
        t3 = OtherTransaction(asset_id=1)
        self.a.transactions = [t1, t2, t3]

        b1 = OtherBody(id=1)
        b2 = OtherBody(id=2)
        b3 = OtherBody(id=3)
        self.a.bodies = [b1, b2, b3]

        db.session.commit()

        # Удаление транзакций, тел актива и актива
        self.a.delete()
        db.session.commit()

        self.assertEqual(self.a.transactions, [])
        self.assertEqual(self.a.bodies, [])
        self.assertEqual(self.p.other_assets, [])


class TestOtherTransactionModel(unittest.TestCase):
    """Класс для тестирования методов транзакции офлайн актива"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.u = User(email='test@test', password='dog')
        db.session.add(self.u)

        # Тикеры
        self.ticker = Ticker(id='usdt', name='USDT', price=0.9)
        db.session.add(self.ticker)

        # Портфель
        self.p = Portfolio(id=1)
        self.u.portfolios = [self.p]

        # Актив портфеля
        self.a = OtherAsset(id=1, portfolio_id=1)
        db.session.add(self.a)

        # Транзакция
        self.t = OtherTransaction(asset_id=1)
        db.session.add(self.t)

        self.date = datetime.now()
        self.comment = 'Comment'

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit(self):
        form = {'date': self.date,
                'type': 'Profit',
                'amount_ticker_id': 'usdt',
                'amount': '1000',
                'comment': self.comment}

        self.t.edit(form)

        self.assertEqual(self.t.date, self.date + timedelta(seconds=time.timezone))
        self.assertEqual(self.t.type, 'Profit')
        self.assertEqual(self.t.amount_ticker, self.ticker)
        self.assertEqual(self.t.amount, 1000)
        self.assertEqual(self.t.amount_usd, 900)
        self.assertEqual(self.t.comment, self.comment)

    def test_update_dependencies(self):
        self.t.amount_usd = 1000
        self.t.asset.cost_now = 500

        # Применить транзакцию
        self.t.update_dependencies()
        self.assertEqual(self.t.asset.cost_now, 1500)

        # Отменить транзакцию
        self.t.update_dependencies('cancel')
        self.assertEqual(self.t.asset.cost_now, 500)

    def test_delete(self):
        self.t.amount_usd = 1000
        self.t.asset.cost_now = 1500

        # Удалить транзакцию
        self.t.delete()
        self.assertEqual(self.t.asset.cost_now, 500)


class TestOtherBodyModel(unittest.TestCase):
    """Класс для тестирования методов тела офлайн актива"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.u = User(email='test@test', password='dog')
        db.session.add(self.u)

        # Тикеры
        self.ticker = Ticker(id='usdt', name='USDT', price=0.9)
        db.session.add(self.ticker)

        # Портфель
        self.p = Portfolio(id=1)
        self.u.portfolios = [self.p]

        # Актив портфеля
        self.a = OtherAsset(id=1, portfolio_id=1)
        db.session.add(self.a)

        # Тело актива
        self.b = OtherBody(asset_id=1)
        db.session.add(self.b)

        self.date = datetime.now()
        self.comment = 'Comment'

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit(self):
        form = {'date': self.date,
                'amount_ticker_id': 'usdt',
                'cost_now_ticker_id': 'usdt',
                'name': 'Name',
                'amount': '1000',
                'cost_now': '1500',
                'comment': self.comment}

        self.b.edit(form)

        self.assertEqual(self.b.date, self.date + timedelta(seconds=time.timezone))
        self.assertEqual(self.b.amount_ticker, self.ticker)
        self.assertEqual(self.b.cost_now_ticker, self.ticker)
        self.assertEqual(self.b.amount, 1000)
        self.assertEqual(self.b.amount_usd, 900)
        self.assertEqual(self.b.cost_now, 1500)
        self.assertEqual(self.b.cost_now_usd, 1350)
        self.assertEqual(self.b.comment, self.comment)

    def test_update_dependencies(self):
        self.b.amount_usd = 1000
        self.b.cost_now_usd = 500
        self.b.asset.amount = 1500
        self.b.asset.cost_now = 500

        # Применить транзакцию
        self.b.update_dependencies()
        self.assertEqual(self.b.asset.amount, 2500)
        self.assertEqual(self.b.asset.cost_now, 1000)

        # Отменить
        self.b.update_dependencies('cancel')
        self.assertEqual(self.b.asset.amount, 1500)
        self.assertEqual(self.b.asset.cost_now, 500)

    def test_delete(self):
        self.b.amount_usd = 1000
        self.b.cost_now_usd = 500
        self.b.asset.amount = 1500
        self.b.asset.cost_now = 500

        # Удалить
        self.b.delete()
        self.assertEqual(self.b.asset.amount, 500)
        self.assertEqual(self.b.asset.cost_now, 0)


class TestTickerModel(unittest.TestCase):
    """Класс для тестирования методов тикера"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Тикеры
        self.ticker = Ticker(id='usdt', name='USDT', price=0.9)
        db.session.add(self.ticker)

        db.session.commit()

        self.date = datetime.now()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit(self):
        form = {'id': 'usd',
                'symbol': 'USD',
                'name': 'Dollar',
                'stable': 'true'}

        self.ticker.edit(form)

        self.assertEqual(self.ticker.id, 'usd')
        self.assertEqual(self.ticker.symbol, 'USD')
        self.assertEqual(self.ticker.name, 'Dollar')
        self.assertEqual(self.ticker.stable, True)

    def test_set_price(self):
        # Добавляем исторические данные
        h = PriceHistory(date=self.date, price_usd=0.8)
        self.ticker.history.append(h)

        # Цена после изменений
        self.ticker.set_price(self.date, 0.5)
        self.assertEqual(h.price_usd, 0.5)

    def test_get_history_price(self):
        # Нет истории
        price = self.ticker.get_history_price(self.date)
        self.assertEqual(price, None)

        # Добавляем исторические данные
        self.ticker.history.append(PriceHistory(date=self.date, price_usd=0.8))

        # Получаем исторические данные
        price = self.ticker.get_history_price(self.date)
        self.assertEqual(price, 0.8)

    def test_delete(self):
        h = PriceHistory(date=self.date, price_usd=0.8)
        self.ticker.history.append(h)
        db.session.commit()

        # Удаление
        self.ticker.delete()
        db.session.commit()

        self.assertEqual(self.ticker.history, [])
        # self.assertEqual(self.ticker, None)
        # self.assertEqual(h, None)


class TestPortfolioModel(unittest.TestCase):
    """Класс для тестирования методов портфеля"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Портфели
        self.p1 = Portfolio(id=1)
        self.p2 = Portfolio(id=2)
        self.p3 = Portfolio(id=3)

        # Пользователь
        self.u = User(email='test@test', password='dog')
        db.session.add(self.u)
        self.u.portfolios = [self.p1, self.p2, self.p3]
        db.session.commit()

        self.date = datetime.now()
        self.comment = 'Comment'

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit(self):
        # Без данных
        form = {}

        self.p1.edit(form)

        self.assertEqual(self.p1.name, None)
        self.assertEqual(self.p1.percent, 0)
        self.assertEqual(self.p1.comment, None)

        # С данными
        self.p1.name = 'Name'
        form = {'market': 'crypto',
                'name': 'Name',
                'percent': '10',
                'comment': self.comment}

        self.p1.edit(form)

        self.assertEqual(self.p1.name, 'Name2')
        self.assertEqual(self.p1.percent, 10)
        self.assertEqual(self.p1.comment, self.comment)

    def test_is_empty(self):
        # Пустой портфель
        self.assertEqual(self.p1.is_empty(), True)

        # Портфель с комментарием
        self.p1.comment = 'Comment'
        self.assertEqual(self.p1.is_empty(), False)
        self.p1.comment = ''
        self.assertEqual(self.p1.is_empty(), True)

        # Портфель с активом
        a = Asset(portfolio_id=1)
        self.p1.assets = [a]
        self.assertEqual(self.p1.is_empty(), False)
        self.p1.assets = []
        self.assertEqual(self.p1.is_empty(), True)

        # Портфель с офлайн активом
        a = OtherAsset(portfolio_id=1)
        self.p1.other_assets = [a]
        self.assertEqual(self.p1.is_empty(), False)
        self.p1.other_assets = []
        self.assertEqual(self.p1.is_empty(), True)

    def test_update_price(self):
        # Asset
        a1 = Asset(ticker=Ticker(id='btc', name='Bitcoin', price=26000),
                   quantity=0.5, amount=5000)
        a2 = Asset(ticker=Ticker(id='eth', name='Ethereum', price=2400),
                   quantity=0.5, in_orders=1000)
        a3 = Asset(ticker=Ticker(id='ltc', name='Litecoin', price=200),
                   quantity=0.5, amount=3000)
        self.p1.assets.extend([a1, a2, a3])
        db.session.commit()

        self.p1.update_price()

        self.assertEqual(self.p1.cost_now, 14300)
        self.assertEqual(self.p1.in_orders, 1000)
        self.assertEqual(self.p1.amount, 8000)

        # OtherAsset
        a1 = OtherAsset(cost_now=6000, amount=5000)
        a2 = OtherAsset(cost_now=1000, amount=500)
        a3 = OtherAsset(cost_now=4000, amount=5000)
        self.p2.other_assets.extend([a1, a2, a3])
        db.session.commit()

        self.p2.update_price()

        self.assertEqual(self.p2.cost_now, 11000)
        self.assertEqual(self.p2.amount, 10500)

    def test_delete(self):
        # Asset
        a1 = Asset(ticker_id='btc')
        a2 = Asset(ticker_id='eth')
        a3 = Asset(ticker_id='ltc')
        self.p1.assets.extend([a1, a2, a3])
        db.session.commit()

        # Удаление
        self.p1.delete()
        db.session.commit()

        self.assertEqual(self.p1.assets, [])

        # OtherAsset
        a1 = OtherAsset()
        a2 = OtherAsset()
        a3 = OtherAsset()
        self.p2.other_assets.extend([a1, a2, a3])
        db.session.commit()

        # Удаление
        self.p2.delete()
        db.session.commit()

        self.assertEqual(self.p2.other_assets, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
