import unittest

from flask import current_app

from tests import app, db, Ticker
from ..models import User
from ..utils import create_new_user, find_user, get_demo_user, login, register


class TestUserUtils(unittest.TestCase):
    """Тесты авторизации."""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(id=1, email='test@test', password='dog')
        self.user.currency_ticker = Ticker(id='usd', symbol='USD', price=1)
        self.user.currency = 'usd'
        self.user.locale = 'ru'
        db.session.add(self.user)
        db.session.commit()

        # Login
        # with self.app.test_request_context():
        #     login_user(self.user)

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_find_user_by_email(self):
        """Тест поиска пользователя по Email."""
        self.assertEqual(find_user_by_email('test@test'), self.user)
        self.assertEqual(find_user_by_email('other@test'), None)

    def test_find_user_by_id(self):
        """Тест поиска по ID и загрузки пользователя."""
        self.assertEqual(find_user(1), self.user)
        self.assertEqual(find_user('1'), self.user)
        self.assertEqual(find_user(2), None)

    def test_create_new_user(self):
        """Тест создания нового пользователя."""

        new_user = create_new_user('test2@test2', 'dog')

        self.assertEqual(find_user_by_email('test2@test2'), new_user)
        self.assertEqual(len(new_user.wallets), 1)
        self.assertEqual(new_user.currency, 'usd')
        self.assertEqual(new_user.currency_ticker_id,
                         current_app.config['CURRENCY_PREFIX'] + new_user.currency)
        self.assertEqual(new_user.locale, 'en')
        self.assertTrue(new_user.info)

    def test_register(self):
        """Тест обработки формы регистрации."""

        with self.app.test_request_context():
            data = {'email': 'sdf@asd', 'password': '1234', 'password2': ''}
            self.assertEqual(register(data), None)

            data = {'email': 'test@test', 'password': 'dog', 'password2': 'dog'}
            self.assertEqual(register(data), None)

            data = {'email': 'te@te', 'password': 'dog', 'password2': 'dog2'}
            self.assertEqual(register(data), None)

            data = {'email': 'test2@test2', 'password': 'dog', 'password2': 'dog'}
            self.assertEqual(register(data), True)

    def test_login(self):
        """Тест обработки формы входа."""
        self.user.set_password('dog')

        with self.app.test_request_context():
            data = {'email': 'test@test', 'password': ''}
            self.assertEqual(login(data), None)

            data = {'email': 'test@test', 'password': '123'}
            self.assertEqual(login(data), None)

            data = {'email': 'test@test', 'password': 'dog'}
            self.assertEqual(login(data), True)

    def test_get_demo_user(self):
        demo_user = User(email='1@1', password='123', type='demo')
        db.session.add(demo_user)
        db.session.commit()

        self.assertEqual(get_demo_user(), demo_user)
