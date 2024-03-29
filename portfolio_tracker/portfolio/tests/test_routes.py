from datetime import datetime
import unittest
from flask import url_for

from flask_login import login_user

from portfolio_tracker.app import db
from portfolio_tracker.portfolio.models import Asset, OtherAsset, OtherBody, \
    OtherTransaction, Portfolio, Ticker, Transaction
from portfolio_tracker.user.models import User
from portfolio_tracker.wallet.models import Wallet, WalletAsset
from tests import app


class TestPortfolioRoutes(unittest.TestCase):
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

    def test_portfolios(self):
        url = url_for('portfolio.portfolios')

        # Тикеры
        btc = Ticker(id='btc', symbol='btc', name='btc', price=30000)
        eth = Ticker(id='eth', symbol='eth', name='eth', price=3000)
        aapl = Ticker(id='aapl', symbol='aapl', name='aapl', price=450)
        db.session.add_all([btc, eth, aapl])

        # Активы
        a1 = Asset(ticker_id='btc', quantity=0.5, amount=10000, in_orders=1000)
        a2 = Asset(ticker_id='eth', quantity=2, amount=4000, in_orders=500)
        a3 = Asset(ticker_id='aapl', quantity=3, amount=900)

        # Офлайн активы
        oa1 = OtherAsset(cost_now=3000, amount=3500)
        oa2 = OtherAsset(cost_now=4300, amount=4000)
        oa3 = OtherAsset(cost_now=0, amount=0)

        # Портфели
        p1 = Portfolio(id=1, name='Первый портфель')
        p2 = Portfolio(id=2, name='Второй портфель', assets=[a1, a2, a3])
        p3 = Portfolio(id=3, name='Третий портфель', other_assets=[oa1, oa2, oa3])
        self.user.portfolios = [p1, p2, p3]
        db.session.commit()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Добавить портфель', 'utf-8'), response.data)
        self.assertIn(bytes('Первый портфель', 'utf-8'), response.data)
        self.assertIn(bytes('Второй портфель', 'utf-8'), response.data)
        self.assertIn(bytes('Третий портфель', 'utf-8'), response.data)

    def test_portfolios_action(self):
        url = url_for('portfolio.portfolios_action')

        # Портфели
        p1 = Portfolio(id=1)
        p2 = Portfolio(id=2, assets=[Asset()])
        p3 = Portfolio(id=3, comment='Comment')
        p4 = Portfolio(id=4, other_assets=[OtherAsset()])
        self.user.portfolios = [p1, p2, p3, p4]
        db.session.commit()

        # Не удалять ести портфель не пустой
        data = {'action': 'delete_if_empty', 'ids': ['1', '2', '3', '4']}
        response = self.client.post(url, json=data, follow_redirects=True)
        self.assertEqual(self.user.portfolios, [p2, p3, p4])
        self.assertIn(b'', response.data)

        # Удалить ести портфель не пустой, но action == delete
        data = {'action': 'delete', 'ids': ['1', '2', '3', '4']}
        response = self.client.post(url, json=data, follow_redirects=True)
        self.assertEqual(self.user.portfolios, [])
        self.assertIn(b'', response.data)

    def test_portfolio_settings(self):
        url = url_for('portfolio.portfolio_settings')

        # Портфели
        self.user.portfolios = [Portfolio(id=1)]
        db.session.commit()

        # Создание портфеля
        response = self.client.get(url, query_string={'portfolio_id': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Добавить портфель', 'utf-8'), response.data)

        # Изменение портфеля
        response = self.client.get(url, query_string={'portfolio_id': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Изменить портфель', 'utf-8'), response.data)

    def test_portfolio_settings_update(self):
        url = url_for('portfolio.portfolio_settings')

        # Создание портфеля
        data = {'name': 'Первый портфель', 'market': 'stocks'}
        response = self.client.post(url, data=data, follow_redirects=True)
        self.assertIn(b'', response.data)
        portfolio = self.user.portfolios[0]
        self.assertEqual(portfolio.name, 'Первый портфель')
        self.assertEqual(portfolio.market, 'stocks')

    def test_portfolio_info(self):

        # Тикеры
        ticker1 = Ticker(id='btc', symbol='btc', market='crypto', price=26000)
        ticker2 = Ticker(id='eth', symbol='eth', market='crypto', price=1600)
        ticker3 = Ticker(id='aapl', symbol='aapl', market='stocks', price=300)

        # Активы
        a1 = Asset(ticker=ticker1, quantity=0.5, amount=10000, in_orders=1000)
        a2 = Asset(ticker=ticker2, quantity=2, amount=4000, in_orders=500)
        a3 = Asset(ticker=ticker3, quantity=3, amount=900)

        # Офлайн активы
        oa1 = OtherAsset(cost_now=3000, amount=3500)
        oa2 = OtherAsset(cost_now=4300, amount=4000)
        oa3 = OtherAsset(cost_now=0, amount=0)

        # Портфели
        p1 = Portfolio(id=1, market='stocks', name='Первый портфель',
                       assets=[a3])
        p2 = Portfolio(id=2, market='crypto', name='Второй портфель',
                       assets=[a1, a2])
        p3 = Portfolio(id=3, market='other', name='Третий портфель',
                       other_assets=[oa1, oa2, oa3])
        p4 = Portfolio(id=4, market='crypto', name='Третий портфель')
        self.user.portfolios = [p1, p2, p3, p4]
        db.session.commit()

        # Нет портфеля
        url = url_for('portfolio.portfolio_info', portfolio_id=5)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        # Пустой портфель
        url = url_for('portfolio.portfolio_info', portfolio_id=4)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Пока ничего', 'utf-8'), response.data)

        # Other портфель
        url = url_for('portfolio.portfolio_info', portfolio_id=3)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Третий портфель', 'utf-8'), response.data)

        # Stocks портфель
        url = url_for('portfolio.portfolio_info', portfolio_id=2)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Второй портфель', 'utf-8'), response.data)

        # Crypto портфель
        url = url_for('portfolio.portfolio_info', portfolio_id=1)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('Первый портфель', 'utf-8'), response.data)

    def test_assets_action(self):
        url = url_for('portfolio.assets_action')

        # Портфель и активы
        a1 = Asset(id=1)
        a2 = Asset(id=2)
        a3 = Asset(id=3, ticker=Ticker(id='btc', name='btc'), comment='Com')

        p = Portfolio(id=1, assets=[a1, a2, a3])
        self.user.portfolios = [p]
        db.session.commit()

        # Не удалять, ести актив не пустой
        data = {'action': 'delete_if_empty', 'ids': ['1', '2', '3']}
        response = self.client.post(url, json=data, follow_redirects=True,
                                    query_string={'portfolio_id': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'', response.data)
        self.assertEqual(p.assets, [a3])

        # Удалить, ести актив не пустой, но action == delete
        data = {'action': 'delete', 'ids': ['1', '2', '3']}
        response = self.client.post(url, json=data, follow_redirects=True,
                                    query_string={'portfolio_id': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'', response.data)
        self.assertEqual(p.assets, [])

    def test_asset_add_modal(self):
        # Тикеры
        t1 = Ticker(id='btc', market='crypto')
        t2 = Ticker(id='eth', market='crypto')
        t3 = Ticker(id='ltc', market='crypto')

        t4 = Ticker(id='aapl', market='stocks')
        t5 = Ticker(id='st-v', market='stocks')
        t6 = Ticker(id='st-r', market='stocks')

        db.session.add_all([t1, t2, t3, t4, t5, t6])
        db.session.commit()

        url = url_for('portfolio.asset_add_modal', market='crypto')
        response = self.client.get(url, query_string={'portfolio_id': '1'})
        self.assertEqual(response.status_code, 200)

        # Crypto
        url = url_for('portfolio.asset_add_tickers', market='crypto')
        response = self.client.get(url, query_string={'portfolio_id': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('btc', 'utf-8'), response.data)
        self.assertIn(bytes('eth', 'utf-8'), response.data)
        self.assertIn(bytes('ltc', 'utf-8'), response.data)

        # Stocks
        url = url_for('portfolio.asset_add_tickers', market='stocks')
        response = self.client.get(url, query_string={'portfolio_id': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes('aapl', 'utf-8'), response.data)
        self.assertIn(bytes('st-v', 'utf-8'), response.data)
        self.assertIn(bytes('st-r', 'utf-8'), response.data)

    def test_asset_add(self):
        url = url_for('portfolio.asset_add')

        # Портфель и актив
        a = Asset(id=1, ticker=Ticker(id='btc', name='btc'))
        p = Portfolio(id=1, assets=[a])
        self.user.portfolios = [p]
        db.session.add(Ticker(id='eth', name='eth'))
        db.session.commit()

        # Нет тикера - 404
        response = self.client.get(url, query_string={'ticker_id': ''})
        self.assertEqual(response.status_code, 404)

        # Нет портфеля - 404
        response = self.client.get(url, query_string={'ticker_id': 'btc',
                                                      'portfolio_id': '2'})
        self.assertEqual(response.status_code, 404)

        # Существующий актив
        response = self.client.get(url, query_string={'ticker_id': 'btc',
                                                      'portfolio_id': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(p.assets), 1)
        self.assertIn(response.data.decode(), url_for('portfolio.asset_info',
                                                portfolio_id=1, asset_id=1))

        # Новый актив
        response = self.client.get(url, query_string={'ticker_id': 'eth',
                                                      'portfolio_id': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(p.assets), 2)
        self.assertIn(response.data.decode(), url_for('portfolio.asset_info',
                                                portfolio_id=1, asset_id=2))

    def test_asset_settings(self):
        url = url_for('portfolio.asset_settings')

        # Портфель и актив
        a1 = Asset(id=1, ticker=Ticker(id='btc', name='btc'))
        p1 = Portfolio(id=1, assets=[a1], market='crypto')

        a2 = Asset(id=2, ticker=Ticker(id='aapl', name='aapl'))
        p2 = Portfolio(id=2, assets=[a2], market='stocks')

        a3 = OtherAsset(id=1, name='Name')
        p3 = Portfolio(id=3, other_assets=[a3], market='other')

        self.user.portfolios = [p1, p2, p3]
        db.session.commit()

        # Crypto
        response = self.client.get(url, query_string={'asset_id': '1',
                                                      'portfolio_id': '1'})
        self.assertEqual(response.status_code, 200)

        # Stocks
        response = self.client.get(url, query_string={'asset_id': '2',
                                                      'portfolio_id': '2'})
        self.assertEqual(response.status_code, 200)

        # Other
        response = self.client.get(url, query_string={'asset_id': '1',
                                                      'portfolio_id': '3'})
        self.assertEqual(response.status_code, 200)

    def test_asset_settings_update(self):
        url = url_for('portfolio.asset_settings')

        # Портфель и актив
        a1 = Asset(id=1, ticker=Ticker(id='btc', name='btc'))
        p1 = Portfolio(id=1, assets=[a1], market='crypto')

        a2 = Asset(id=2, ticker=Ticker(id='aapl', name='aapl'))
        p2 = Portfolio(id=2, assets=[a2], market='stocks')

        a3 = OtherAsset(id=1, name='Name')
        p3 = Portfolio(id=3, other_assets=[a3], market='other')

        self.user.portfolios = [p1, p2, p3]
        db.session.commit()

        # Нет актива(crypto, stocks) - 404
        data = {'name': 'Name'}
        response = self.client.post(url, json=data, follow_redirects=True,
                                    query_string={'asset_id': '2',
                                                  'portfolio_id': '1'})
        self.assertEqual(response.status_code, 404)

        # Нет актива(other) - 200
        data = {'name': 'Name'}
        response = self.client.post(url, json=data, follow_redirects=True,
                                    query_string={'asset_id': '2',
                                                  'portfolio_id': '1'})
        self.assertEqual(response.status_code, 404)

    def test_asset_info(self):
        url = url_for('portfolio.asset_info')

        # Тикеры
        btc = Ticker(id='btc', symbol='btc', name='btc', price=30000)
        aapl = Ticker(id='aapl', symbol='aapl', name='aapl', price=450)
        db.session.add_all([btc, aapl])

        # Crypto портфель
        t1 = Transaction(ticker_id='btc', ticker2_id='usd',
                         quantity=0.5, quantity2=13000,
                         price=26000, price_usd=26000, date=datetime.now(),
                         type='buy', portfolio_id=1, order=False)

        a1 = Asset(id=1, ticker_id='btc', transactions=[t1])
        p1 = Portfolio(id=1, assets=[a1], market='crypto')

        # Sticks портфель
        t2 = Transaction(ticker_id='aapl', ticker2_id='usd',
                         quantity=1.5, quantity2=300,
                         price=200, price_usd=200, date=datetime.now(),
                         type='buy', portfolio_id=2, order=False)

        a2 = Asset(id=2, ticker_id='aapl', transactions=[t2])
        p2 = Portfolio(id=2, assets=[a2], market='stocks')

        # Other портфель
        ot = OtherTransaction(date=datetime.now(), asset_id=1, amount=3000,
                              amount_ticker_id='usd', amount_usd=3000,
                              type='profit')
        ob = OtherBody(name='Name', date=datetime.now(), asset_id=1,
                       amount=3000, amount_ticker_id='usd', amount_usd=3000,
                       cost_now=4000, cost_now_ticker_id='usd', cost_now_usd=4000)
        a3 = OtherAsset(id=1, name='Name', transactions=[ot], bodies=[ob])
        p3 = Portfolio(id=3, other_assets=[a3], market='other')

        self.user.portfolios = [p1, p2, p3]
        db.session.commit()

        # Crypto
        response = self.client.get(url, query_string={'asset_id': '1',
                                                      'portfolio_id': '1'})
        self.assertEqual(response.status_code, 200)

        # Stocks
        response = self.client.get(url, query_string={'asset_id': '2',
                                                      'portfolio_id': '2'})
        self.assertEqual(response.status_code, 200)

        # Other
        response = self.client.get(url, query_string={'asset_id': '1',
                                                      'portfolio_id': '3'})
        self.assertEqual(response.status_code, 200)

    def test_transaction_info(self):
        url = url_for('portfolio.transaction_info')

        # Портфель
        t = Transaction(id=1, ticker_id='btc', ticker2_id='usd',
                        quantity=0.5, quantity2=13000,
                        price=26000, price_usd=26000, date=datetime.now(),
                        wallet_id=1,
                        type='buy', portfolio_id=1, order=False)

        a = Asset(id=1,
                  ticker=Ticker(id='btc', symbol='btc', price=30000),
                  transactions=[t])
        p = Portfolio(id=1, assets=[a], market='crypto')

        self.user.portfolios = [p]

        wa = WalletAsset(ticker_id='btc', quantity=2)
        w1 = Wallet(id=1, name='BuyWalletName')
        w2 = Wallet(id=2, name='SellWalletName', wallet_assets=[wa])
        self.user.wallets = [w1, w2]
        db.session.commit()

        # Нет актива
        response = self.client.get(url, query_string={'asset_id': '2',
                                                      'portfolio_id': '1'})
        self.assertEqual(response.status_code, 404)

        # Новая транзакция
        response = self.client.get(url, query_string={'asset_id': '1',
                                                      'portfolio_id': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(a.transactions), 1)
        self.assertIn(b'name="price" autocomplete="off" value="30000.0', response.data)
        self.assertIn(bytes('class="btn btn-outline-active btn-sm" for="btnradio1">Покупка', 'utf-8'), response.data)
        self.assertIn(b'selected value="1">BuyWalletName', response.data)
        self.assertIn(b'selected value="2">SellWalletName', response.data)
        self.assertIn(b'selected value="usd">USD', response.data)


