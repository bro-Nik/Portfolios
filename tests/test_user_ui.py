import unittest
from unittest.mock import MagicMock, patch

from flask import session
from flask_login import login_user

from tests import app, db
from portfolio_tracker.user.models import User
from portfolio_tracker.user.services.ui import get_currency, get_locale, get_timezone


class TestUserUI(unittest.TestCase):

    def setUp(self):
        # self.user = MockUser()

        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Создаем тестовые данные
        self.user = User(id=1, email='1@1', password='')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_locale_authenticated(self):
        # Пользователь аутентифицирован, локаль задана
        self.user.locale = 'ru'

        with app.test_request_context():
            login_user(self.user, False)

            locale = get_locale()
            self.assertEqual(locale, 'ru')

    def test_get_locale_not_authenticated(self):
        # Пользователь не аутентифицирован, локаль из сессии
        with app.test_request_context():
            session['locale'] = 'fr'

            locale = get_locale()
            self.assertEqual(locale, 'fr')

    @patch('portfolio_tracker.user.services.ui.request', new_callable=MagicMock)
    def test_get_locale_accept_language(self, mock_request):
        # Локаль из заголовка Accept-Language
        with app.test_request_context():
            session.pop('locale', None)
            mock_request.accept_languages.best_match.return_value = 'es'

            locale = get_locale()
            self.assertEqual(locale, 'es')

    @patch('portfolio_tracker.user.services.ui.request', new_callable=MagicMock)
    def test_get_locale_default(self, mock_request):
        # Локаль по умолчанию
        with app.test_request_context():
            session.pop('locale', None)
            mock_request.accept_languages.best_match.return_value = None

            locale = get_locale()
            self.assertEqual(locale, 'en')

    def test_get_currency_authenticated(self):
        # Пользователь аутентифицирован, валюта задана
        self.user.currency = 'eur'
        with app.test_request_context():
            login_user(self.user, False)

            currency = get_currency()
            self.assertEqual(currency, 'eur')

    def test_get_currency_not_authenticated(self):
        # Пользователь не аутентифицирован, валюта из сессии
        with app.test_request_context():
            session['currency'] = 'gbp'

            currency = get_currency()
            self.assertEqual(currency, 'gbp')

    def test_get_currency_default(self):
        # Валюта по умолчанию
        with app.test_request_context():
            session.pop('currency', None)

            currency = get_currency()
            self.assertEqual(currency, 'usd')

    def test_get_timezone_authenticated(self):
        # Пользователь аутентифицирован, часовой пояс задан
        self.user.timezone = 'Europe/Moscow'
        with app.test_request_context():
            login_user(self.user, False)

            timezone = get_timezone()
            self.assertEqual(timezone, 'Europe/Moscow')

    def test_get_timezone_not_authenticated(self):
        # Пользователь не аутентифицирован
        with app.test_request_context():
            timezone = get_timezone()
            self.assertIsNone(timezone)

if __name__ == '__main__':
    unittest.main(verbosity=2)
