import unittest
from flask import url_for

from flask_login import login_user

from tests import app, db, User, Ticker
from ..models import Alert, WatchlistAsset


class TestPortfolioRoutes(unittest.TestCase):
    """Класс для тестирования функций портфелей"""
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.user = User(id=1, email='test@test', password='dog')
        db.session.add(self.user)
        self.user.currency_ticker = Ticker(id='usd', symbol='USD', price=1)
        self.user.currency = 'usd'
        self.user.locale = 'ru'
        db.session.commit()

        # Login
        with self.app.test_request_context():
            login_user(self.user)

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_assets(self):
        url = url_for('watchlist.assets')

        # Тикеры
        btc = Ticker(id='btc', symbol='BTC_Symbol', name='BTC_Name', market='crypto')
        eth = Ticker(id='eth', symbol='ETH_Symbol', name='ETH_Name', market='crypto')
        aapl = Ticker(id='aapl', symbol='AAPL_Symbol', name='AAPL_Name', market='stocks')
        db.session.add_all([btc, eth, aapl])

        # Активы
        asset1 = WatchlistAsset(ticker=btc, alerts=[Alert(price=24000, price_usd=210),
                                                    Alert(price=20000, price_usd=190)])
        asset2 = WatchlistAsset(ticker=eth, comment='ETH_Comment')
        asset3 = WatchlistAsset(ticker=aapl, alerts=[Alert(price=300, price_usd=320)])
        self.user.watchlist = [asset1, asset2, asset3]
        db.session.commit()

        # Crypto
        response = self.client.get(url, query_string={'market': 'crypto'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'BTC_SYMBOL', response.data)
        self.assertIn(b'BTC_Name', response.data)
        self.assertIn(b'210,00', response.data)
        self.assertIn(b'190,00', response.data)

        self.assertIn(b'ETH_Name', response.data)
        self.assertIn(b'ETH_SYMBOL', response.data)
        self.assertIn(b'ETH_Comment', response.data)

        # Stocks
        response = self.client.get(url, query_string={'market': 'stocks'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'AAPL_SYMBOL', response.data)
        self.assertIn(b'AAPL_Name', response.data)
        self.assertIn(b'320,00', response.data)

    def test_assets_action(self):
        url = url_for('watchlist.assets_action')

        asset1 = WatchlistAsset(id=1, ticker_id='btc')
        asset2 = WatchlistAsset(id=2, ticker_id='eth', comment='Comment')
        asset3 = WatchlistAsset(id=3, ticker_id='aapl', alerts=[Alert(transaction_id=1)])
        self.user.watchlist = [asset1, asset2, asset3]
        db.session.commit()

        # Не удалять, ести актив не пустой
        data = {'action': 'delete_if_empty', 'ids': ['1', '2', '3']}
        response = self.client.post(url, json=data, follow_redirects=True)
        self.assertEqual(self.user.watchlist, [asset2, asset3])
        self.assertIn(b'', response.data)

        # Удалить, ести актив не пустой, но action == delete
        data = {'action': 'delete', 'ids': ['1', '2', '3']}
        response = self.client.post(url, json=data, follow_redirects=True)
        self.assertEqual(self.user.watchlist, [])
        self.assertIn(b'', response.data)

    def test_asset_add(self):
        url = url_for('watchlist.asset_add')

        # Тикер
        btc = Ticker(id='btc', symbol='BTC_Symbol', name='BTC_Name')
        db.session.add(btc)

        # Нет тикера - 404
        response = self.client.get(url, query_string={'ticker_id': 'None'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.user.watchlist, [])

        # Добавление тикера
        response = self.client.get(url, query_string={'ticker_id': 'btc'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.watchlist[0].ticker_id, 'btc')

    def test_watchlist_asset_update(self):
        url = url_for('watchlist.watchlist_asset_update')

        # Тикер
        btc = Ticker(id='btc', symbol='BTC_Symbol', name='BTC_Name')
        db.session.add(btc)

        # Нет тикера - 404
        data = {'comment': 'Comment'}
        response = self.client.post(url, json=data,
                                    query_string={'ticker_id': 'None'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.user.watchlist, [])

        # Добавление тикера
        data = {'comment': 'Comment'}
        response = self.client.post(url, json=data,
                                    query_string={'ticker_id': 'btc'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.watchlist[0].ticker_id, 'btc')

    def test_asset_info(self):
        url = url_for('watchlist.asset_info')

        # Тикеры
        btc = Ticker(id='btc', symbol='BTC_Symbol', name='BTC_Name')
        eth = Ticker(id='eth', symbol='ETH_Symbol', name='ETH_Name')
        aapl = Ticker(id='aapl', symbol='AAPL_Symbol', name='AAPL_Name')
        db.session.add_all([btc, eth, aapl])

        # Активы
        asset1 = WatchlistAsset(ticker=btc,
                                alerts=[Alert(price=400, price_usd=390), Alert(price=200, price_usd=210)])
        asset2 = WatchlistAsset(ticker=aapl, alerts=[Alert(price=300, price_usd=320)])
        self.user.watchlist = [asset1, asset2]
        db.session.commit()

        # Нет тикера - 404
        response = self.client.get(url, query_string={'ticker_id': 'None'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.user.watchlist, [asset1, asset2])

        #
        response = self.client.get(url, query_string={'ticker_id': 'btc'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'210,00', response.data)
        self.assertIn(b'390,00', response.data)

    def test_alerts_action(self):
        url = url_for('watchlist.alerts_action')

        alert1 = Alert(id=1)
        alert2 = Alert(id=2)
        alert3 = Alert(id=3)
        asset = WatchlistAsset(id=1, ticker_id='btc',
                               alerts=[alert1, alert2, alert3])
        self.user.watchlist = [asset]
        db.session.commit()

        # Удалить
        data = {'action': 'delete', 'ids': ['1', '2', '3']}
        response = self.client.post(url, json=data, query_string={'ticker_id': 'btc'})
        self.assertEqual(asset.alerts, [])
        self.assertIn(b'', response.data)

    def test_alert_info(self):
        url = url_for('watchlist.alert_info')

        # Тикер
        btc = Ticker(id='btc', symbol='BTC_Symbol', name='BTC_Name')
        db.session.add_all([btc])

        alert = Alert(id=1, price=200, price_usd=0, price_ticker_id='usd',
                      type='down', comment='Comment', status='on')
        asset = WatchlistAsset(id=1, ticker_id='btc', alerts=[alert])
        self.user.watchlist = [asset]
        db.session.commit()

        response = self.client.get(url, query_string={'ticker_id': 'btc'})
        self.assertEqual(response.status_code, 200)

    def test_alert_update(self):
        url = url_for('watchlist.alert_update')

        # Тикер
        btc = Ticker(id='btc', price=20000)
        usdt = Ticker(id='usdt', price=0.8)
        db.session.add_all([btc, usdt])

        asset = WatchlistAsset(id=1, ticker_id='btc')
        self.user.watchlist = [asset]
        db.session.commit()

        data = {'price': 200, 'price_ticker_id': 'usdt', 'comment': 'Comment'}
        response = self.client.post(url, data=data, query_string={'ticker_id': 'btc'})
        self.assertEqual(response.status_code, 200)
        alert = self.user.watchlist[0].alerts[0]
        self.assertEqual(alert.price, 200)
        self.assertEqual(alert.price_ticker, usdt)
        self.assertEqual(alert.price_usd, 250)
        self.assertEqual(alert.type, 'down')
