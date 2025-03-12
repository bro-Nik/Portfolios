import unittest

from flask_login import login_user

from tests import app, db
from portfolio_tracker.user.models import User
from portfolio_tracker.portfolio.models import Asset, OtherAsset, Portfolio, Ticker


class TestPortfolio(unittest.TestCase):
    """Класс для тестирования методов портфеля"""

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_profit(self):
        portfolio = Portfolio(id=1)
        portfolio.cost_now = 1000
        portfolio.amount = 900

        self.assertEqual(portfolio.profit, 100)

    def test_is_empty(self):
        p = Portfolio(id=1, comment='', transactions=[])

        # Пустой портфель
        self.assertEqual(p.is_empty, True)

        # Портфель с комментарием
        p.comment = 'Comment'
        self.assertEqual(p.is_empty, False)
        p.comment = ''
        self.assertEqual(p.is_empty, True)

        # Портфель с активом
        p.assets = [Asset()]
        self.assertEqual(p.is_empty, False)
        p.assets = []
        self.assertEqual(p.is_empty, True)

        # Портфель с офлайн активом
        p.other_assets = [OtherAsset()]
        self.assertEqual(p.is_empty, False)
        p.other_assets = []
        self.assertEqual(p.is_empty, True)


class TestPortfolioService(unittest.TestCase):
    """Класс для тестирования методов портфеля"""

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Создаем тестовые данные
        self.user = User(id=1, email='1@1', password='')
        self.portfolio = Portfolio(id=1, user_id=1, market='crypto', name='Test Portfolio')
        self.user.portfolios.append(self.portfolio)
        db.session.add(self.user)

        self.btc = Ticker(id='btc', name='Bitcoin', price=26000, symbol='btc', market='crypto')
        self.eth = Ticker(id='eth', name='Ethereum', price=2400, symbol='eth', market='crypto')
        self.ltc = Ticker(id='ltc', name='Litecoin', price=200, symbol='eth', market='crypto')
        db.session.add_all([self.btc, self.eth, self.ltc])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit_empty_form(self):
        form = {}
        self.portfolio.service.edit(form)

        self.assertEqual(self.portfolio.name, 'Test Portfolio')
        self.assertEqual(self.portfolio.percent, 0)
        self.assertEqual(self.portfolio.comment, '')

    def test_edit(self):
        form = {'name': 'New Name', 'comment': 'New Comment', 'percent': 50}
        self.portfolio.service.edit(form)

        self.assertEqual(self.portfolio.name, 'New Name')
        self.assertEqual(self.portfolio.comment, 'New Comment')
        self.assertEqual(self.portfolio.percent, 50)

    def test_edit_duplicate_name(self):
        portfolio = Portfolio(id=2, user_id=1, name='Portfolio', market='crypto')
        self.user.portfolios.append(portfolio)

        form = {'name': 'Test Portfolio'}
        portfolio.service.edit(form)

        self.assertEqual(portfolio.name, 'Test Portfolio2')

    def test_update_info(self):
        # Asset
        asset1 = Asset(ticker_id='btc', quantity=0.5, amount=5000)
        asset2 = Asset(ticker_id='eth', quantity=0.5, buy_orders=1000)
        asset3 = Asset(ticker_id='ltc', quantity=0.5, amount=3000)
        self.portfolio.assets.extend([asset1, asset2, asset3])
        db.session.commit()

        self.portfolio.service.update_info()

        self.assertEqual(self.portfolio.cost_now, 14300)
        self.assertEqual(self.portfolio.buy_orders, 1000)
        self.assertEqual(self.portfolio.amount, 8000)
        self.assertEqual(self.portfolio.invested, 8000)
        

    def test_update_info_other(self):
        # Меняем рынок на 'other'
        self.portfolio.market = 'other'

        # OtherAsset
        other_asset1 = OtherAsset(name='Asset1', cost_now=6000, amount=5000)
        other_asset2 = OtherAsset(name='Asset2', cost_now=1000, amount=500)
        other_asset3 = OtherAsset(name='Asset3', cost_now=4000, amount=5000)
        self.portfolio.other_assets.extend([other_asset1, other_asset2, other_asset3])
        db.session.commit()

        self.portfolio.service.update_info()

        self.assertEqual(self.portfolio.cost_now, 11000)
        self.assertEqual(self.portfolio.amount, 10500)

    def test_get_asset_by_id(self):
        asset = Asset(id=1, portfolio_id=1, ticker_id='btc')
        self.portfolio.assets.append(asset)
        db.session.commit()

        asset = self.portfolio.service.get_asset(find_by=1)

        self.assertIsNotNone(asset)
        self.assertEqual(asset.id, 1)
        self.assertEqual(asset.ticker_id, 'btc')

    def test_get_asset_by_ticker_id(self):
        asset = Asset(id=1, portfolio_id=1, ticker_id='btc')
        self.portfolio.assets.append(asset)
        db.session.commit()

        asset = self.portfolio.service.get_asset(find_by='btc')

        self.assertIsNotNone(asset)
        self.assertEqual(asset.ticker_id, 'btc')

    def test_get_other_asset_by_id(self):
        # Меняем рынок на 'other'
        self.portfolio.market = 'other'
        other_asset = OtherAsset(id=1, portfolio_id=1, name='OtherAsset')
        self.portfolio.other_assets.append(other_asset)
        db.session.commit()

        asset = self.portfolio.service.get_asset(1)

        self.assertIsNotNone(asset)
        self.assertEqual(asset.id, 1)

    def test_create_asset_if_not_found(self):
        asset = self.portfolio.service.get_asset(find_by='btc', create=True)

        self.assertIsNotNone(asset)
        self.assertEqual(asset.ticker_id, 'btc')

    def test_get_asset_not_found(self):
        asset = self.portfolio.service.get_asset(find_by=999)

        self.assertIsNone(asset)

    def test_create_market_asset(self):
        asset = self.portfolio.service.create_asset(ticker_id='btc')

        self.assertIsNotNone(asset)
        self.assertEqual(asset.ticker_id, 'btc')
        self.assertEqual(asset.portfolio_id, 1)

    def test_create_other_asset(self):
        # Меняем рынок на 'other'
        self.portfolio.market = 'other'
        asset = self.portfolio.service.create_asset(ticker_id=None)

        self.assertIsNotNone(asset)
        self.assertEqual(asset.portfolio_id, 1)
        self.assertIsInstance(asset, OtherAsset)

    def test_create_asset_duplicate_ticker_id(self):
        # Создаем актив с ticker_id = 'BTC'
        asset = Asset(id=1, portfolio_id=1, ticker_id='btc')
        self.portfolio.assets.append(asset)
        db.session.commit()

        asset = self.portfolio.service.create_asset(ticker_id='btc')

        self.assertIsNone(asset)  # Актив не должен создаваться, если ticker_id уже существует

    def test_delete_if_empty(self):
        # Портфель пустой (нет активов и комментария)
        with app.test_request_context():
            login_user(self.user, False)
            self.portfolio.service.delete_if_empty()

            # Проверяем, что портфель удален
            self.assertIsNone(db.session.get(Portfolio, 1))

    def test_do_not_delete_if_not_empty_assets(self):
        # Добавляем актив
        asset = Asset(id=1, portfolio_id=1, ticker_id='btc')
        self.portfolio.assets.append(asset)
        db.session.commit()

        with app.test_request_context():
            login_user(self.user, False)
            self.portfolio.service.delete_if_empty()

            # Проверяем, что портфель не удален
            self.assertIsNotNone(db.session.get(Portfolio, 1))

    def test_do_not_delete_if_not_empty_other_assets(self):
        # Меняем рынок на 'other' и добавляем актив
        self.portfolio.market = 'other'
        other_asset = OtherAsset(id=1, portfolio_id=1, name='OtherAsset')
        self.portfolio.other_assets.append(other_asset)
        db.session.commit()

        with app.test_request_context():
            login_user(self.user, False)
            self.portfolio.service.delete_if_empty()

            # Проверяем, что портфель не удален
            self.assertIsNotNone(db.session.get(Portfolio, 1))

    def test_do_not_delete_if_comment_exists(self):
        # Добавляем комментарий
        self.portfolio.comment = "Test comment"
        db.session.commit()

        with app.test_request_context():
            login_user(self.user, False)
            self.portfolio.service.delete_if_empty()

            # Проверяем, что портфель не удален
            self.assertIsNotNone(db.session.get(Portfolio, 1))

    def test_delete_portfolio_with_assets(self):
        # Создаем активы
        asset1 = Asset(id=1, portfolio_id=1, ticker_id='btc')
        asset2 = Asset(id=2, portfolio_id=1, ticker_id='eth')
        self.portfolio.assets.extend([asset1, asset2])
        db.session.commit()

        self.portfolio.service.delete()

        # Проверяем, что портфель и активы удалены
        self.assertIsNone(db.session.get(Portfolio, 1))
        assets = db.session.execute(db.select(Asset).filter_by(portfolio_id=1)).all()
        self.assertEqual(len(assets), 0)

    def test_delete_portfolio_with_other_assets(self):
        # Меняем рынок на 'other'
        self.portfolio.market = 'other'
        other_asset1 = OtherAsset(id=1, portfolio_id=1, name='OtherAsset')
        other_asset2 = OtherAsset(id=2, portfolio_id=1, name='OtherAsset2')
        self.portfolio.other_assets.extend([other_asset1, other_asset2])
        db.session.commit()

        self.portfolio.service.delete()

        # Проверяем, что портфель и активы удалены
        self.assertIsNone(db.session.get(Portfolio, 1))
        other_assets = db.session.execute(db.select(OtherAsset).filter_by(portfolio_id=1)).all()
        self.assertEqual(len(other_assets), 0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
