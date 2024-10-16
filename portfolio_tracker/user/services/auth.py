from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json

from flask_login import current_user, login_user
from flask_babel import gettext

from portfolio_tracker.app import redis
from portfolio_tracker.repository import Repository
from portfolio_tracker.wallet.models import Wallet
from ..models import User, UserInfo
from ..repository import UserRepository
from .user import UserService
from .ui import get_locale


def login(form: dict) -> tuple[bool, list]:
    """Обработка формы входа. Вход пользовалетя."""
    email = form.get('email')
    password = form.get('password')
    redis_key = 'user_auth'

    # Поля не заполнены
    if not email or not password:
        message = [gettext('Введити адрес электронной почты и пароль'), 'warning']
        return False, message

    # Поиск прошлых попыток входа
    login_attempts = redis.hget(redis_key, email)
    if login_attempts:
        login_attempts = json.loads(login_attempts.decode())
    if not isinstance(login_attempts, dict):
        login_attempts = {}

    # Проверка на блокировку входа
    block_time = login_attempts.get('next_try_time')
    if block_time:
        block_time = datetime.strptime(block_time, '%Y-%m-%d %H:%M:%S.%f%z')
        delta = (block_time - datetime.now(timezone.utc)).total_seconds()
        if delta > 0:
            m = int(delta // 60)
            s = delta - 60 * m if m else delta

            message = [gettext('Вход заблокирован. '
                       'Осталось %(m)s мин. %(s)s сек.', m=m, s=round(s)),
                       'warning']
            return False, message

    user = UserRepository.get(email=email)

    # Пользователь не найден
    if not user:
        message = [gettext('Неверный адрес электронной почты или пароль'), 'warning'] 
        return False, message

    us = UserService(user)

    # Проверка пройдена
    if us.check_password(password):
        login_user(user, form.get('remember-me', False))
        us.new_login()
        redis.hdel(redis_key, email)
        return True, []

    # Проверка не пройдена
    message = [gettext('Неверный адрес электронной почты или пароль'), 'warning']

    login_attempts.setdefault('count', 0)
    login_attempts['count'] += 1
    if login_attempts['count'] >= 5:
        next_try = datetime.now(timezone.utc) + timedelta(minutes=10)
        login_attempts['next_try_time'] = str(next_try)
        message = [gettext('Вход заблокирован на 10 минут'), 'warning']

    redis.hset(redis_key, email, json.dumps(login_attempts))
    return False, message


def register(form: dict) -> tuple[bool, list | dict]:
    """Обработка формы регистрации. Регистрация пользователя."""
    email = form.get('email')
    password = form.get('password')
    password2 = form.get('password2')

    # Поля не заполнены
    if not (email and password and password2):
        m = 'Заполните адрес электронной почты, пароль и подтверждение пароля'
        return False, [gettext(m), 'warning']

    if UserRepository.get(email=email):
        return False, [gettext('Данный почтовый ящик уже используется'), 'warning']

    if password != password2:
        return False, [gettext('Пароли не совпадают'), 'warning']

    user = UserRepository.create(email=email)
    us = UserService(user)

    us.set_password(password)
    us.change_currency()
    us.change_locale(get_locale())
    Wallet.create()
    user.info = UserInfo()
    Repository.add(user)
    Repository.save()
    return True, [gettext('Вы зарегистрированы. Теперь войдите в систему')]


def change_password(form: dict, user: User = current_user):
    """Обработка формы смены пароля."""

    us = UserService(user)

    # Проверка старого пароля
    if us.check_password(form.get('old_pass', '')):
        new_pass = form.get('new_pass')
        # Пароль с подтверждением совпадают
        if new_pass and new_pass == form.get('new_pass2'):
            us.set_password(new_pass)
            return True, [gettext('Пароль обновлен')]
        return False, [gettext('Новые пароли не совпадают'), 'warning']

    return False, [gettext('Не верный старый пароль'), 'warning']
