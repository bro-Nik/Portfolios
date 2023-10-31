import unittest

from flask import current_app

from portfolio_tracker.app import db, create_app
from portfolio_tracker.models import Portfolio, User, Wallet
from portfolio_tracker.settings import Config
from portfolio_tracker.watchlist.watchlist import watchlist_asset_update

app = create_app()


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'


class TestUser(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()


    def tearDown(self):
        db.session.remove()
        db.drop_all()


    def test_create_new_user(self):
        self.assertEqual(db.session.execute(db.select(User)).scalar(), None)
        u = User.create_new_user('test@test', 'dog')
        self.assertEqual(db.session.execute(db.select(User)).scalar(), u)

        self.assertEqual(len(u.wallets), 1)
        self.assertEqual(u.currency, 'usd')
        self.assertEqual(u.currency_ticker_id, current_app.config['CURRENCY_PREFIX'] + u.currency)
        self.assertEqual(u.locale, 'en')
        self.assertTrue(u.info)


    def test_password_hashing(self):
        u = User.create_new_user('test@test', 'dog')

        u.set_password('cat')
        self.assertFalse(u.check_password('dog'))
        self.assertTrue(u.check_password('cat'))


    def test_update_assets(self):
        u = User.create_new_user('test@test', 'dog')

        u.portfolios = [Portfolio(name='Test', market='crypto'), ]
        u.wallets = [Wallet(name='Test'), ]

        u.update_assets()


    def test_cleare(self):
        u = User.create_new_user('test@test', 'dog')

        u.portfolios = [Portfolio(name='Test', market='crypto'), ]
        u.wallets = [Wallet(name='Test'), ]
        db.session.commit()

        u.cleare()

        self.assertEqual(len(u.portfolios), 0)
        self.assertEqual(len(u.wallets), 0)


    def test_delete(self):
        u = User.create_new_user('test@test', 'dog')
        self.assertEqual(db.session.execute(db.select(User)).scalar(), u)

        u.portfolios = [Portfolio(name='Test', market='crypto'), ]
        u.wallets = [Wallet(name='Test'), ]
        db.session.commit()

        u.delete()

        self.assertEqual(len(u.portfolios), 0)
        self.assertEqual(len(u.wallets), 0)
        self.assertEqual(db.session.execute(db.select(User)).scalar(), None)


    def test_export(self):
        u = User.create_new_user('test@test', 'dog')

        u.portfolios = [Portfolio(name='Test', market='crypto'), ]
        u.wallets = [Wallet(name='Test'), ]

        data = u.export_data()
        self.assertEqual(len(data['portfolios']), 1)
        self.assertEqual(len(data['wallets']), 1)


    def test_import(self):
        u = User.create_new_user('test@test', 'dog')

        p1 = Portfolio(name='Test', market='crypto')
        w1 = Wallet(name='Test')

        u.portfolios = [p1, ]
        u.wallets = [w1, ]

        data = u.export_data()
        u.import_data(data)
        
        self.assertEqual(len(u.portfolios), 2)
        self.assertEqual(len(u.wallets), 2)
        self.assertEqual(u.portfolios[0], p1)
        self.assertEqual(u.wallets[0], w1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
