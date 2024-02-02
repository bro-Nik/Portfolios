import unittest

from werkzeug.security import check_password_hash

from tests import app, db, Asset, Portfolio, Ticker, Transaction, Wallet, \
    WalletAsset
from ..models import User


class TestUserModel(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(id=1, email='test@test', password='dog')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_set_password(self):
        self.user.set_password('new_pass')

        self.assertTrue(check_password_hash(self.user.password, 'new_pass'))

    def test_check_password(self):
        self.user.set_password('dog')
        self.assertTrue(self.user.check_password('dog'))
        self.assertFalse(self.user.check_password('cat'))

    def test_change_currency(self):
        self.user.change_currency('rub')
        self.assertEqual(self.user.currency, 'rub')
        self.assertEqual(self.user.currency_ticker_id, 'rub')

    def test_change_locale(self):
        self.user.change_locale('ru')
        self.assertEqual(self.user.locale, 'ru')

    def test_update_assets(self):
        # Тикеры
        btc = Ticker(id='btc', market='crypto')
        usdt = Ticker(id='usdt', market='crypto', stable=True)
        db.session.add_all([btc, usdt])

        # Активы
        p_asset = Asset(ticker_id='btc')
        w_asset1 = WalletAsset(ticker_id='btc')
        w_asset2 = WalletAsset(ticker_id='usdt')

        portfolio = Portfolio(id=1, assets=[p_asset])
        wallet = Wallet(id=1, wallet_assets=[w_asset1, w_asset2])

        self.user.portfolios = [portfolio]
        self.user.wallets = [wallet]

        t1 = Transaction(ticker_id='btc', quantity=0.5, ticker2_id='usdt',
                         quantity2=13000, price=26000, price_usd=26000,
                         type='Buy', wallet_id=1, portfolio_id=1, order=False)

        t2 = Transaction(ticker_id='btc', quantity=0.5, ticker2_id='usdt',
                         quantity2=13000, price=26000, price_usd=26000,
                         type='Buy', wallet_id=1, portfolio_id=1, order=True)
        db.session.add_all([t1, t2])
        db.session.commit()

        self.user.update_assets()

        self.assertEqual(p_asset.quantity, 0.5)
        self.assertEqual(p_asset.in_orders, 13000)
        self.assertEqual(p_asset.amount, 13000)

        self.assertEqual(w_asset1.quantity, 0.5)
        self.assertEqual(w_asset2.quantity, 13000)
        self.assertEqual(w_asset1.buy_orders, 13000)
        self.assertEqual(w_asset1.sell_orders, 0)

    def test_cleare(self):
        # Тикеры
        btc = Ticker(id='btc', market='crypto')
        usdt = Ticker(id='usdt', market='crypto', stable=True)
        db.session.add_all([btc, usdt])

        # Активы
        p_asset = Asset(ticker_id='btc')
        w_asset1 = WalletAsset(ticker_id='btc')
        w_asset2 = WalletAsset(ticker_id='usdt')

        portfolio = Portfolio(id=1, assets=[p_asset])
        wallet = Wallet(id=1, wallet_assets=[w_asset1, w_asset2])

        self.user.portfolios = [portfolio]
        self.user.wallets = [wallet]

        t1 = Transaction(ticker_id='btc', quantity=0.5, ticker2_id='usdt',
                         quantity2=13000, price=26000, price_usd=26000,
                         type='Buy', wallet_id=1, portfolio_id=1, order=False)

        t2 = Transaction(ticker_id='btc', quantity=0.5, ticker2_id='usdt',
                         quantity2=13000, price=26000, price_usd=26000,
                         type='Buy', wallet_id=1, portfolio_id=1, order=True)
        db.session.add_all([t1, t2])
        db.session.commit()

        self.user.cleare()

        self.assertEqual(self.user.portfolios, [])
        self.assertEqual(self.user.wallets, [])
        self.assertEqual(self.user.watchlist, [])

    def test_delete(self):
        self.user.delete()

        self.assertEqual(db.session.execute(db.select(User)).scalar(), None)

    def test_make_admin(self):
        self.user.make_admin()
        self.assertEqual(self.user.type, 'admin')

    def test_unmake_admin(self):
        self.user.unmake_admin()
        self.assertEqual(self.user.type, '')
