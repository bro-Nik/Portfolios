import unittest

from flask import current_app
from tests import app

from . import db, User
from .utils import check_password, create_new_user, find_user, load_user, \
    set_password


class TestAuth(unittest.TestCase):
    """Тесты авторизации."""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.u = User(id=1, email='test@test', password='dog')
        db.session.add(self.u)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_find_user(self):
        """Тест поиска пользователя по Email."""
        self.assertEqual(find_user('test@test'), self.u)
        self.assertEqual(find_user('other@test'), None)

    def test_load_user(self):
        """Тест поиска по ID и загрузки пользователя."""
        self.assertEqual(load_user(1), self.u)
        self.assertEqual(load_user(2), None)

    def test_create_new_user(self):
        """Тест создания нового пользователя."""
        user = create_new_user('test2@test2', 'dog')

        self.assertEqual(find_user('test2@test2'), user)
        self.assertEqual(len(user.wallets), 1)
        self.assertEqual(user.currency, 'usd')
        self.assertEqual(user.currency_ticker_id,
                         current_app.config['CURRENCY_PREFIX'] + user.currency)
        self.assertEqual(user.locale, 'en')
        self.assertTrue(user.info)

    def test_password_hashing(self):
        """Тест изменения и проврки пароля."""
        set_password(self.u, 'cat')
        self.assertFalse(check_password(self.u.password, 'dog'))
        self.assertTrue(check_password(self.u.password, 'cat'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
