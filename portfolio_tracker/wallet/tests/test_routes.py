from datetime import datetime
import unittest
from flask import url_for

from flask_login import current_user, login_user

from portfolio_tracker.app import db
from portfolio_tracker.portfolio.models import Asset, OtherAsset, OtherBody, \
    OtherTransaction, Portfolio, Ticker, Transaction
from portfolio_tracker.user.models import User
from portfolio_tracker.wallet.models import Wallet, WalletAsset
from tests import app


class TestWalletRoutes(unittest.TestCase):
    """Класс для тестирования функций портфелей"""
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.user = User(email='test@test', password='dog')
        self.user.currency_ticker = Ticker(id='usd', symbol='USD', price=1)
        self.user.currency = 'usd'
        self.user.locale = 'ru'
        db.session.add(self.user)
        db.session.commit()

        # Login
        with self.app.test_request_context():
            login_user(self.user)

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_wallets(self):
        url = url_for('wallet.wallets')

        # Тикеры
        btc = Ticker(id='btc', symbol='btc', name='btc', price=30000)
        eth = Ticker(id='eth', symbol='eth', name='eth', price=3000)
        aapl = Ticker(id='aapl', symbol='aapl', name='aapl', price=450)
        db.session.add_all([btc, eth, aapl])

        # Активы
        a1 = WalletAsset(ticker_id='btc', quantity=0.5, sell_orders=0.2)
        a2 = WalletAsset(ticker_id='eth', quantity=2, buy_orders=500)
        a3 = WalletAsset(ticker_id='aapl', quantity=3)

        # Кошельки
        w1 = Wallet(id=1, name='Первый кошелек')
        w2 = Wallet(id=2, name='Второй кошелек', wallet_assets=[a1, a2])
        w3 = Wallet(id=3, name='Третий кошелек', wallet_assets=[a3])
        self.user.wallets = [w1, w2, w3]
        db.session.commit()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Добавить кошелек', 'utf-8'), response.data)
        self.assertIn(bytes('Первый кошелек', 'utf-8'), response.data)
        self.assertIn(bytes('Второй кошелек', 'utf-8'), response.data)
        self.assertIn(bytes('Третий кошелек', 'utf-8'), response.data)

    def test_wallets_action(self):
        url = url_for('wallet.wallets_action')

        # Кошельки
        w1 = Wallet(id=1)
        w2 = Wallet(id=2, wallet_assets=[WalletAsset()])
        w3 = Wallet(id=3, comment='Comment')
        w4 = Wallet(id=4, transactions=[Transaction()])
        self.user.wallets = [w1, w2, w3, w4]
        db.session.commit()

        # Не удалять ести кошелек не пустой
        data = {'action': 'delete_if_empty', 'ids': ['1', '2', '3', '4']}
        response = self.client.post(url, json=data, follow_redirects=True)
        self.assertEqual(self.user.wallets, [w2, w3, w4])
        self.assertIn(b'', response.data)

        # Удалить ести кошелек не пустой, но action == delete
        data = {'action': 'delete', 'ids': ['1', '2', '3', '4']}
        response = self.client.post(url, json=data, follow_redirects=True)
        self.assertEqual(len(self.user.wallets), 1)
        self.assertEqual(len(self.user.wallets[0].wallet_assets), 1)
        self.assertEqual(self.user.wallets[0].wallet_assets[0].ticker_id, 'usd')
        self.assertIn(b'', response.data)

    def test_wallet_settings(self):
        url = url_for('wallet.wallet_settings')

        # Кошельки
        self.user.wallets = [Wallet(id=1)]
        db.session.commit()

        # Создание кошелька
        response = self.client.get(url, query_string={'wallet_id': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Добавить кошелек', 'utf-8'), response.data)

        # Изменение кошелька
        response = self.client.get(url, query_string={'wallet_id': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Изменить кошелек', 'utf-8'), response.data)

    def test_wallet_settings_update(self):
        url = url_for('wallet.wallet_settings')

        # Создание кошелька
        data = {'name': 'Первый кошелек'}
        response = self.client.post(url, data=data, follow_redirects=True)
        self.assertIn(b'', response.data)
        wallet = self.user.wallets[0]
        self.assertEqual(wallet.name, 'Первый кошелек')

    def test_wallet_info(self):
        url = url_for('wallet.wallet_info')

        # Тикеры
        btc = Ticker(id='btc', symbol='btc', name='btc', price=30000)
        eth = Ticker(id='eth', symbol='eth', name='eth', price=3000)
        aapl = Ticker(id='aapl', symbol='aapl', name='aapl', price=450)
        usdt = Ticker(id='usdt', symbol='usdt', name='usdt', price=0.98, stable=True)
        db.session.add_all([btc, eth, aapl, usdt])

        # Активы
        a1 = WalletAsset(ticker_id='btc', quantity=0.5, sell_orders=0.2)
        a2 = WalletAsset(ticker_id='eth', quantity=2, buy_orders=500)
        a3 = WalletAsset(ticker_id='aapl', quantity=3)
        a4 = WalletAsset(ticker_id='usdt', quantity=3000)

        # Кошельки
        w1 = Wallet(id=1, name='Первый кошелек')
        w2 = Wallet(id=2, name='Второй кошелек', wallet_assets=[a1, a2, a3])
        w3 = Wallet(id=3, name='Третий кошелек', wallet_assets=[a4])
        self.user.wallets = [w1, w2, w3]
        db.session.commit()

        # Нет кошелька
        response = self.client.get(url, query_string={'wallet_id': '4'})
        self.assertEqual(response.status_code, 404)

        # Пустой кошельк
        response = self.client.get(url, query_string={'wallet_id': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Пока ничего', 'utf-8'), response.data)
        self.assertIn(bytes('Первый кошелек', 'utf-8'), response.data)

        # Кошельк с активами
        response = self.client.get(url, query_string={'wallet_id': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Второй кошелек', 'utf-8'), response.data)

        # Кошельк с активами (stable)
        response = self.client.get(url, query_string={'wallet_id': '3'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Третий кошелек', 'utf-8'), response.data)

    def test_assets_action(self):
        url = url_for('wallet.assets_action')

        # Кошелек и активы
        db.session.add(Ticker(id='btc', name='BTC'))
        db.session.add(Transaction(ticker_id='btc', wallet_id=2))

        a1 = WalletAsset(id=1)
        a2 = WalletAsset(id=2, ticker_id='btc', wallet_id=2)
        a3 = WalletAsset(id=3)

        w = Wallet(id=2, wallet_assets=[a1, a2, a3])
        self.user.wallets = [w]
        db.session.commit()

        # Не удалять, ести актив не пустой
        data = {'action': 'delete_if_empty', 'ids': ['1', '2', '3']}
        response = self.client.post(url, json=data, follow_redirects=True,
                                    query_string={'wallet_id': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'', response.data)
        self.assertEqual(w.assets, [a2])

        # Удалить, ести актив не пустой, но action == delete
        data = {'action': 'delete', 'ids': ['1', '2', '3']}
        response = self.client.post(url, json=data, follow_redirects=True,
                                    query_string={'wallet_id': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'', response.data)
        self.assertEqual(w.assets, [])

    def test_asset_info(self):
        url = url_for('wallet.asset_info')

        # Тикеры
        btc = Ticker(id='btc', symbol='btc', name='btc', price=30000)
        eth = Ticker(id='eth', symbol='eth', name='eth', price=3000)
        aapl = Ticker(id='aapl', symbol='aapl', name='aapl', price=450)
        db.session.add_all([btc, eth, aapl])

        # Актив
        t1 = Transaction(ticker_id='btc', ticker2_id='usd',
                         quantity=0.5, quantity2=13000,
                         price=26000, price_usd=26000, date=datetime.now(),
                         type='buy', portfolio_id=1, wallet_id=1, order=False)
        a1 = WalletAsset(id=1, ticker_id='btc', quantity=0.5, sell_orders=0.2)
        w1 = Wallet(id=1, name='Первый кошелек', wallet_assets=[a1])

        # Актив stable
        t2 = Transaction(ticker_id='btc', ticker2_id='usd',
                         quantity=0.5, quantity2=13000,
                         price=26000, price_usd=26000, date=datetime.now(),
                         type='buy', portfolio_id=1, wallet_id=2, order=False)
        a2 = WalletAsset(id=2, ticker_id='eth', quantity=2, buy_orders=500)
        w2 = Wallet(id=2, name='Второй кошелек', wallet_assets=[a2])

        db.session.add_all([t1, t2])
        self.user.wallets = [w1, w2]
        db.session.commit()

        # Актив
        response = self.client.get(url, query_string={'asset_id': '1',
                                                      'wallet_id': '1'})
        self.assertEqual(response.status_code, 200)

        # Актив stable
        response = self.client.get(url, query_string={'asset_id': '2',
                                                      'wallet_id': '2'})
        self.assertEqual(response.status_code, 200)

    def test_stable_add_modal(self):
        # Тикеры
        t1 = Ticker(id='btc', market='crypto', stable=True)
        t2 = Ticker(id='eth', market='crypto', stable=True)
        t3 = Ticker(id='ltc', market='crypto', stable=True)

        db.session.add_all([t1, t2, t3])
        db.session.commit()

        url = url_for('wallet.stable_add_modal')
        response = self.client.get(url, query_string={'wallet_id': '1'})
        self.assertEqual(response.status_code, 200)

        url = url_for('wallet.stable_add_tickers')
        response = self.client.get(url, query_string={'wallet_id': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('btc', 'utf-8'), response.data)
        self.assertIn(bytes('eth', 'utf-8'), response.data)
        self.assertIn(bytes('ltc', 'utf-8'), response.data)

    def test_stable_add(self):
        url = url_for('wallet.stable_add')

        # Кошелек и актив
        db.session.add_all([Ticker(id='btc', name='BTC'),
                            Ticker(id='usdt', name='USDT')])

        a = WalletAsset(id=1, ticker_id='btc')
        w = Wallet(id=2, wallet_assets=[a])
        self.user.wallets = [w]
        db.session.commit()

        # Нет тикера - 404
        response = self.client.get(url, query_string={'ticker_id': ''})
        self.assertEqual(response.status_code, 404)

        # Нет кошелька - 404
        response = self.client.get(url, query_string={'ticker_id': 'btc',
                                                      'wallet_id': '1'})
        self.assertEqual(response.status_code, 404)

        # Существующий актив
        response = self.client.get(url, query_string={'ticker_id': 'btc',
                                                      'wallet_id': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(w.assets), 1)
        self.assertIn(response.data.decode(), url_for('wallet.asset_info',
                                                      wallet_id=2,
                                                      ticker_id='btc'))

        # Новый актив
        response = self.client.get(url, query_string={'ticker_id': 'usdt',
                                                      'wallet_id': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(w.assets), 2)
        self.assertIn(response.data.decode(), url_for('wallet.asset_info',
                                                      wallet_id=2,
                                                      ticker_id='usdt'))

    def test_transaction_info(self):
        url = url_for('wallet.transaction_info')

        # Тикеры
        btc = Ticker(id='btc', symbol='btc', name='btc', price=30000)
        eth = Ticker(id='eth', symbol='eth', name='eth', price=3000)
        db.session.add_all([btc, eth])

        # Актив
        t = Transaction(id=2, ticker_id='btc', ticker2_id='usd',
                        quantity=0.5, quantity2=13000,
                        price=26000, price_usd=26000, date=datetime.now(),
                        type='buy', portfolio_id=1, wallet_id=1, order=False)
        db.session.add(t)

        a = WalletAsset(id=1, ticker_id='btc', quantity=0.5, sell_orders=0.2)
        w = Wallet(id=1, name='Первый кошелек', wallet_assets=[a])

        self.user.wallets = [w]
        db.session.commit()

        # Нет актива
        response = self.client.get(url, query_string={'asset_id': '2',
                                                      'wallet_id': '1'})
        self.assertEqual(response.status_code, 404)

        # Новая транзакция
        response = self.client.get(url, query_string={'asset_id': '1',
                                                      'wallet_id': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(a.transactions), 1)

    def test_transaction_update(self):
        pass

    def test_transactions_action(self):
        pass
