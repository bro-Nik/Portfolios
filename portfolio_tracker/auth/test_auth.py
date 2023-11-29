import unittest

from flask import current_app

from portfolio_tracker.app import db
from portfolio_tracker.auth.utils import create_new_user, load_user
from portfolio_tracker.models import User
from tests import app


class TestAuth(unittest.TestCase):
    """Тесты авторизации."""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_load_user(self):
        """Тест загрузки пользователя."""
        u = User(id=1, email='test@test', password='dog')
        db.session.add(u)
        db.session.commit()

        self.assertEqual(load_user(1), u)

    def test_create_new_user(self):
        """Тест создания пользователя."""
        self.assertEqual(db.session.execute(db.select(User)).scalar(), None)
        u = create_new_user('test@test', 'dog')

        self.assertEqual(db.session.execute(db.select(User)).scalar(), u)
        self.assertEqual(len(u.wallets), 1)
        self.assertEqual(u.currency, 'usd')
        self.assertEqual(u.currency_ticker_id,
                         current_app.config['CURRENCY_PREFIX'] + u.currency)
        self.assertEqual(u.locale, 'en')
        self.assertTrue(u.info)


if __name__ == '__main__':
    unittest.main(verbosity=2)
