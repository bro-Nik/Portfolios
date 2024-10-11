import json
import unittest

from flask import url_for
from flask_login import login_user, logout_user
from flask_login import FlaskLoginClient
from werkzeug.security import generate_password_hash

from tests import app, db, Ticker, User, Alert, WatchlistAsset, Wallet, \
    WalletAsset


class TestApiRoutes(unittest.TestCase):
    def setUp(self):
        app.test_client_class = FlaskLoginClient
        self.app = app
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.user = User(email='user@test', password=generate_password_hash('dog'))
        self.user.currency_ticker = Ticker(id='usd', symbol='USD', price=1)
        self.user.currency = 'usd'
        self.user.locale = 'ru'

        # Демо Пользователь
        self.demo_user = User(email='demo@test', password='dog', type='demo')
        self.demo_user.currency_ticker = Ticker(id='usdt', symbol='USDT', price=0.9)
        self.demo_user.currency = 'usdt'
        self.demo_user.locale = 'ru'
        db.session.add_all([self.user, self.demo_user])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_worked_alerts_count(self):
        url = url_for('api.worked_alerts_count')

        asset1 = WatchlistAsset(alerts=[Alert(status='worked'), Alert(status='worked'),
                                Alert(status='on'), Alert(status='off')])
        asset2 = WatchlistAsset(alerts=[Alert(status='worked'), Alert(status='worked'),
                                Alert(status='on'), Alert(status='off')])
        asset3 = WatchlistAsset(alerts=[Alert(status='worked'), Alert(status='worked'),
                                Alert(status='on'), Alert(status='off')])
        self.user.watchlist = [asset1, asset2, asset3]

        with self.app.test_request_context():
            login_user(self.user)
            response = self.client.get(url, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b'<span>6</span>')
            logout_user()

    def test_all_currencies(self):
        url = url_for('api.all_currencies')

        # Тикеры
        db.session.add_all(
            [Ticker(id='usdp', symbol='usdp', name='USDP', market='currency'),
             Ticker(id='usds', symbol='usds', name='USDS', market='currency'),
             Ticker(id='usdx', symbol='usdx', name='USDX', market='currency'),
             Ticker(id='usdd', symbol='usdd', name='USDD', market='currency'),
             Ticker(id='btc', symbol='btc', name='BTC', market='crypto'),
             Ticker(id='eth', symbol='eth', name='ETH', market='crypto'),
             Ticker(id='aapl', symbol='aapl', name='AAPL', market='stocks')
             ])
        db.session.commit()

        result = [{'value': 'usdp', 'text': 'USDP', 'subtext': 'USDP'},
                  {'value': 'usds', 'text': 'USDS', 'subtext': 'USDS'},
                  {'value': 'usdx', 'text': 'USDX', 'subtext': 'USDX'},
                  {'value': 'usdd', 'text': 'USDD', 'subtext': 'USDD'}]

        with self.app.test_request_context():
            login_user(self.user)
            response = self.client.get(url)
            self.assertEqual(json.loads(response.data), result)

    def test_wallets_to_sell(self):
        url = url_for('api.wallets_to_sell')

        # Пустые кошельки
        wallet1 = Wallet(id=1, name='WalletName1')
        wallet2 = Wallet(id=2, name='WalletName2')
        wallet3 = Wallet(id=3, name='WalletName3')
        self.user.wallets = [wallet1, wallet2, wallet3]
        db.session.commit()

        result = {'message': 'В кошельках нет свободных остатков'}

        with self.app.test_request_context():
            login_user(self.user)
            response = self.client.get(url, query_string={'ticker_id': 'btc'})
            self.assertEqual(json.loads(response.data), result)

        # Добавим активы
        asset1 = WalletAsset(ticker_id='btc', quantity=0.5)
        asset2 = WalletAsset(ticker_id='eth', quantity=0.7)
        asset3 = WalletAsset(ticker_id='btc', quantity=2)

        wallet1.assets = [asset1]
        wallet2.assets = [asset2]
        wallet3.assets = [asset3]

        # Тикеры
        db.session.add_all([Ticker(id='btc', symbol='btc'),
                            Ticker(id='eth', symbol='eth')])
        db.session.commit()

        result = [{'value': '3', 'text': 'WalletName3', 'sort': 2.0,
                   'subtext': '(2,00\xa0BTC)'},
                  {'value': '1', 'text': 'WalletName1', 'sort': 0.5,
                   'subtext': '(0,50\xa0BTC)'}]

        with self.app.test_request_context():
            login_user(self.user)
            response = self.client.get(url, query_string={'ticker_id': 'btc'})
            self.assertEqual(json.loads(response.data), result)

    def test_wallets_to_buy(self):
        url = url_for('api.wallets_to_buy')

        # Тикеры
        db.session.add_all([Ticker(id='btc', symbol='btc', price=20000),
                            Ticker(id='usdp', symbol='usdp', price=1, stable=True)])

        # Активы
        asset1 = WalletAsset(ticker_id='btc', quantity=0.5)
        asset2 = WalletAsset(ticker_id='usdp', quantity=500)
        asset3 = WalletAsset(ticker_id='usdp', quantity=2000)

        # Кошельки
        wallet1 = Wallet(id=1, name='WalletName1', wallet_assets=[asset1])
        wallet2 = Wallet(id=2, name='WalletName2', wallet_assets=[asset2])
        wallet3 = Wallet(id=3, name='WalletName3', wallet_assets=[asset3])
        self.user.wallets = [wallet1, wallet2, wallet3]
        db.session.commit()

        result = [{'value': '3', 'text': 'WalletName3', 'sort': 2000.0,
                   'subtext': '(~ 2\xa0000,00\xa0$)'},
                  {'value': '2', 'text': 'WalletName2', 'sort': 500.0,
                   'subtext': '(~ 500,00\xa0$)'},
                  {'value': '1', 'text': 'WalletName1', 'sort': 0,
                   'subtext': '(~ 0,00\xa0$)'}]

        with self.app.test_request_context():
            login_user(self.user)
            response = self.client.get(url)
            self.assertEqual(json.loads(response.data), result)

    def test_wallets_to_transfer_out(self):
        url = url_for('api.wallets_to_transfer_out')

        # Только один кошелек
        asset1 = WalletAsset(ticker_id='btc', quantity=0.5)
        wallet1 = Wallet(id=1, name='WalletName1', wallet_assets=[asset1])
        self.user.wallets = [wallet1]
        db.session.commit()

        result = {'message': 'У вас только один кошелек'}

        with self.app.test_request_context():
            login_user(self.user)
            response = self.client.get(url, query_string={'wallet_id': '1',
                                                          'ticker_id': 'btc'})
            self.assertEqual(json.loads(response.data), result)

        # Добавим кошельки и активы
        asset2 = WalletAsset(ticker_id='eth', quantity=0.7)
        asset3 = WalletAsset(ticker_id='btc', quantity=2)

        wallet2 = Wallet(id=2, name='WalletName2', wallet_assets=[asset2])
        wallet3 = Wallet(id=3, name='WalletName3', wallet_assets=[asset3])
        self.user.wallets = [wallet1, wallet2, wallet3]

        # Тикеры
        db.session.add_all([Ticker(id='btc', symbol='btc'),
                            Ticker(id='eth', symbol='eth')])
        db.session.commit()

        result = [{'value': '3', 'text': 'WalletName3', 'sort': 2.0,
                   'subtext': '(2,00\xa0BTC)'},
                  {'value': '2', 'text': 'WalletName2', 'sort': 0}]

        with self.app.test_request_context():
            login_user(self.user)
            response = self.client.get(url, query_string={'wallet_id': '1',
                                                          'ticker_id': 'btc'})
            self.assertEqual(json.loads(response.data), result)

    def test_wallet_stable_assets(self):
        url = url_for('api.wallet_stable_assets')

        # Тикеры
        db.session.add_all([Ticker(id='btc', symbol='btc', price=20000),
                            Ticker(id='usdp', symbol='usdp', price=1, stable=True),
                            Ticker(id='usds', symbol='usds', price=1, stable=True)])

        # Активы
        asset1 = WalletAsset(ticker_id='usdp', quantity=2300)
        asset2 = WalletAsset(ticker_id='btc', quantity=0.7)
        asset3 = WalletAsset(ticker_id='usds', quantity=4400)

        wallet = Wallet(id=1, name='WalletName1',
                        wallet_assets=[asset1, asset2, asset3])
        self.user.wallets = [wallet]
        db.session.commit()

        result = [{'value': 'usds', 'text': 'USDS', 'subtext': '(~ 4400)',
                   'info': 1.0},
                  {'value': 'usdp', 'text': 'USDP', 'subtext': '(~ 2300)',
                   'info': 1.0}]

        with self.app.test_request_context():
            login_user(self.user)
            response = self.client.get(url, query_string={'wallet_id': '1'})
            self.assertEqual(json.loads(response.data), result)
