from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch

from flask_login import login_user

from tests import app, db
from portfolio_tracker.user.models import User
from portfolio_tracker.user.services.auth import change_password, login, register


class MockRedis:
    def __init__(self):
        self.data = {}

    def hget(self, key, field):
        return json.dumps(self.data.get(field, {})).encode()

    def hset(self, key, field, value):
        self.data[field] = json.loads(value)

    def hdel(self, key, field):
        if field in self.data:
            del self.data[field]


class TestUserAuth(unittest.TestCase):
    """Класс для тестирования методов портфеля"""

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Создаем тестовые данные
        self.user = User(id=1, email='test@example.com')
        self.user.service.set_password('password123')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    @patch('portfolio_tracker.user.services.auth.redis', new_callable=MockRedis)
    def test_login_success(self, mock_redis):
        form = {'email': 'test@example.com', 'password': 'password123', 'remember-me': False}
        with app.test_request_context():
            login_user(self.user, False)
            success, message = login(form)

            self.assertTrue(success)
            self.assertEqual(message, [])

    @patch('portfolio_tracker.user.services.auth.redis', new_callable=MockRedis)
    def test_login_failure_wrong_password(self, mock_redis):
        form = {'email': 'test@example.com', 'password': 'wrongpassword', 'remember-me': False}

        with app.test_request_context():
            login_user(self.user, False)
            success, message = login(form)

            self.assertFalse(success)
            self.assertEqual(message[0], 'Неверный адрес электронной почты или пароль')
            self.assertEqual(message[1], 'warning')

    @patch('portfolio_tracker.user.services.auth.redis', new_callable=MockRedis)
    def test_login_failure_blocked(self, mock_redis):
        mock_redis.data['test@example.com'] = {'count': 5, 'next_try_time': str(datetime.now(timezone.utc) + timedelta(minutes=10))}
        form = {'email': 'test@example.com', 'password': 'wrongpassword', 'remember-me': False}

        with app.test_request_context():
            login_user(self.user, False)
            success, message = login(form)

            self.assertFalse(success)
            self.assertIn('Вход заблокирован', message[0])
            self.assertEqual(message[1], 'warning')

    def test_register_success(self):
        form = {'email': 'new@example.com', 'password': 'password123', 'password2': 'password123'}

        with app.test_request_context():
            login_user(self.user, False)

            success, message = register(form)
            self.assertTrue(success)
            self.assertEqual(message[0], 'Вы зарегистрированы. Теперь войдите в систему')

    def test_register_failure_existing_email(self):
        form = {'email': 'test@example.com', 'password': 'password123', 'password2': 'password123'}

        with app.test_request_context():
            login_user(self.user, False)

            success, message = register(form)
            self.assertFalse(success)
            self.assertEqual(message[0], 'Данный почтовый ящик уже используется')
            self.assertEqual(message[1], 'warning')

    def test_register_failure_password_mismatch(self):
        form = {'email': 'new@example.com', 'password': 'password123', 'password2': 'differentpassword'}

        with app.test_request_context():
            login_user(self.user, False)

            success, message = register(form)
            self.assertFalse(success)
            self.assertEqual(message[0], 'Пароли не совпадают')
            self.assertEqual(message[1], 'warning')

    def test_register_failure_missing_fields(self):
        form = {'email': '', 'password': '', 'password2': ''}

        with app.test_request_context():
            login_user(self.user, False)

            success, message = register(form)
            self.assertFalse(success)
            self.assertEqual(message[0], 'Заполните адрес электронной почты, пароль и подтверждение пароля')
            self.assertEqual(message[1], 'warning')

    def test_change_password_success(self):
        form = {'old_pass': 'password123', 'new_pass': 'newpassword123', 'new_pass2': 'newpassword123'}

        with app.test_request_context():
            login_user(self.user, False)

            success, message = change_password(form, self.user)
            self.assertTrue(success)
            self.assertEqual(message[0], 'Пароль обновлен')

    def test_change_password_failure_wrong_old_password(self):
        form = {'old_pass': 'wrongpassword', 'new_pass': 'newpassword123', 'new_pass2': 'newpassword123'}

        with app.test_request_context():
            login_user(self.user, False)

            success, message = change_password(form, self.user)
            self.assertFalse(success)
            self.assertEqual(message[0], 'Не верный старый пароль')
            self.assertEqual(message[1], 'warning')

    def test_change_password_failure_password_mismatch(self):
        form = {'old_pass': 'password123', 'new_pass': 'newpassword123', 'new_pass2': 'differentpassword'}

        with app.test_request_context():
            login_user(self.user, False)

            success, message = change_password(form, self.user)
            self.assertFalse(success)
            self.assertEqual(message[0], 'Новые пароли не совпадают')
            self.assertEqual(message[1], 'warning')


if __name__ == '__main__':
    unittest.main(verbosity=2)
