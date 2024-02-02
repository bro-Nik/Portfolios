import unittest

from flask import request, url_for
from flask_login import login_user, logout_user
from flask_login import FlaskLoginClient
from werkzeug.security import generate_password_hash
from ..models import User

from tests import app, db, Ticker


class TestUserRoutes(unittest.TestCase):
    def setUp(self):
        app.test_client_class = FlaskLoginClient
        self.app = app
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.user = User(email='user@test', password=generate_password_hash('dog'))
        self.user.currency_ticker = Ticker(id='usd', symbol='USD', price=1)
        self.user.currency = 'usd'
        self.user.locale = 'ru'

        # Демо Пользователь
        self.demo_user = User(email='demo@test', password='dog', type='demo')
        self.demo_user.currency_ticker = Ticker(id='usdt', symbol='USDT', price=0.9)
        self.demo_user.currency = 'usdt'
        self.demo_user.locale = 'ru'
        db.session.add_all([self.user, self.demo_user])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_login(self):
        url = url_for('user.login')

        # Анонимный пользователь получает форму
        with self.app.test_request_context():
            response = self.client.get(url, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(response.request.path, url)

        # Авторизованный пользователь не получает форму
        with self.app.test_request_context():
            login_user(self.user)
            response = self.client.get(url, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(response.request.path, url_for('portfolio.portfolios'))
            logout_user()

        # Демо пользователь получает форму
        with self.app.test_request_context():
            login_user(self.demo_user)
            response = self.client.get(url, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(response.request.path, url)
            logout_user()

        # Отправка формы
        with self.app.test_request_context():
            data = {'email': 'user@test', 'password': 'dog'}
            response = self.client.post(url, data=data, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(response.request.path, url_for('portfolio.portfolios'))

    def test_register(self):
        url = url_for('user.register')

        # Анонимный пользователь получает форму
        with self.app.test_request_context():
            response = self.client.get(url, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(response.request.path, url)

        # Авторизованный пользователь не получает форму
        with self.app.test_request_context():
            login_user(self.user)
            response = self.client.get(url, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(response.request.path, url_for('portfolio.portfolios'))
            logout_user()

        # Демо пользователь получает форму
        with self.app.test_request_context():
            login_user(self.demo_user)
            response = self.client.get(url, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(response.request.path, url)
            logout_user()

        # Отправка формы
        with self.app.test_request_context():
            data = {'email': 'new_user@test', 'password': 'dog', 'password2': 'dog'}
            response = self.client.post(url, data=data, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(response.request.path, url_for('user.login'))

    def test_redirect_to_signin(self):
        url = url_for('portfolio.portfolios')

        # Анонимный пользователь переходит на страницу входа
        with self.app.test_request_context():
            response = self.client.get(url, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(response.request.path, url_for('user.login'))

        # Авторизованный пользователь проходит
        with self.app.test_request_context():
            login_user(self.user)
            response = self.client.get(url, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(response.request.path, url_for('portfolio.portfolios'))
            logout_user()
