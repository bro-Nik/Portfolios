from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json

from flask import current_app
from flask_login import current_user, login_user
from flask_babel import gettext

from portfolio_tracker.app import redis
from portfolio_tracker.repository import Repository
from portfolio_tracker.wallet.models import Wallet
from ..models import User, UserInfo
from ..repository import UserRepository
from .user import UserService
from .ui import get_locale


MAX_LOGIN_ATTEMPTS = 5
BLOCK_TIME_MINUTES = 10


def login(form: dict) -> tuple[bool, list]:
    """Обработка формы входа. Вход пользователя.

    Аргументы:
        form (dict): Словарь, содержащий данные формы входа. 
                     Ожидает ключи 'email' и 'password', 
                     а также опционально 'remember-me'.

    Возвращает:
        tuple[bool, list]: Кортеж, где первый элемент — булево значение, 
                           указывающее на успешность входа, 
                           а второй элемент — список
                           (первый элемент — текст сообщения, 
                           второй элемент — тип сообщения: 'warning' или 'error').

    Примечания:
        - Если пользователь не найден или пароль неверный, 
          возвращается сообщение об ошибке.
        - Если достигнуто максимальное количество попыток входа, 
          пользователь блокируется на заданное время.

    """
    email = form.get('email')
    password = form.get('password')
    redis_key = 'user_auth'

    # Поля не заполнены
    if not email or not password:
        mes = gettext('Введити адрес электронной почты и пароль')
        return False, [mes, 'warning']

    # Поиск прошлых попыток входа
    try:
        login_attempts = redis.hget(redis_key, email)
        if login_attempts:
            login_attempts = json.loads(login_attempts.decode())
        else:
            login_attempts = {}
    except Exception as e:
        # Логгирование ошибки
        current_app.logger.error(f"Ошибка при получении данных из Redis: {e}")
        mes = gettext('Ошибка сервера. Попробуйте позже.')
        return False, [mes, 'error']

    # Проверка на блокировку входа
    block_time = login_attempts.get('next_try_time')
    if block_time:
        block_time = datetime.strptime(block_time, '%Y-%m-%d %H:%M:%S.%f%z')
        delta = (block_time - datetime.now(timezone.utc)).total_seconds()
        if delta > 0:
            m = int(delta // 60)
            s = delta - 60 * m if m else delta

            mes = gettext('Вход заблокирован. '
                          'Осталось %(m)s мин. %(s)s сек.', m=m, s=round(s))
            return False, [mes, 'warning']

    user = UserRepository.get(email=email)

    # Пользователь не найден
    if not user:
        mes = gettext('Неверный адрес электронной почты или пароль') 
        return False, [mes, 'warning']

    us = UserService(user)

    # Проверка пройдена
    if us.check_password(password):
        login_user(user, form.get('remember-me', False))
        us.new_login()
        redis.hdel(redis_key, email)
        return True, []

    # Проверка не пройдена
    mes = gettext('Неверный адрес электронной почты или пароль')

    login_attempts.setdefault('count', 0)
    login_attempts['count'] += 1
    if login_attempts['count'] >= MAX_LOGIN_ATTEMPTS:
        next_try = datetime.now(timezone.utc) + timedelta(minutes=BLOCK_TIME_MINUTES)
        login_attempts['next_try_time'] = str(next_try)
        mes = gettext('Вход заблокирован на %(m)s минут.', m=BLOCK_TIME_MINUTES)

    redis.hset(redis_key, email, json.dumps(login_attempts))
    return False, [mes, 'warning']


def register(form: dict) -> tuple[bool, list]:
    """Обработка формы регистрации. Регистрация пользователя.

    Аргументы:
        form (dict): Словарь, содержащий данные формы регистрации.
                     Ожидает ключи 'email', 'password' и 'password2'.

    Возвращает:
        tuple[bool, list]: Кортеж, где первый элемент — булево значение,
                           указывающее на успешность регистрации,
                           а второй элемент — список 
                           (первый элемент — текст сообщения, 
                           второй элемент — тип сообщения: 'warning' или 'success').

    Примечания:
        - Если регистрация успешна, возвращается сообщение об успешной регистрации.
        - Если произошла ошибка, возвращается соответствующее сообщение об ошибке.

    """
    email = form.get('email')
    password = form.get('password')
    password2 = form.get('password2')

    # Поля не заполнены
    if not (email and password and password2):
        mes = gettext('Заполните адрес электронной почты, '
                      'пароль и подтверждение пароля')
        return False, [mes, 'warning']

    if UserRepository.get(email=email):
        mes = gettext('Данный почтовый ящик уже используется')
        return False, [mes, 'warning']

    if password != password2:
        mes = gettext('Пароли не совпадают')
        return False, [mes, 'warning']

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
    """Обработка формы смены пароля.

    Аргументы:
        form (dict): Словарь, содержащий данные формы смены пароля.
                     Ожидает ключи 'old_pass', 'new_pass' и 'new_pass2'.
        user (User): Объект текущего пользователя (по умолчанию — current_user).

    Возвращает:
        tuple[bool, list | dict]: Кортеж, где первый элемент — булево значение,
                                  указывающее на успешность смены пароля,
                                  а второй элемент — список
                                  (первый элемент — текст сообщения, 
                                  второй элемент — тип сообщения: 'warning' или 'success').

    Примечания:
        - Если смена пароля успешна, возвращается сообщение об успешном обновлении пароля.
        - Если произошла ошибка, возвращается соответствующее сообщение об ошибке.

    """

    us = UserService(user)

    # Проверка старого пароля
    if not us.check_password(form.get('old_pass', '')):
        return False, [gettext('Не верный старый пароль'), 'warning']

    new_pass = form.get('new_pass')
    # Пароль с подтверждением совпадают
    if new_pass and new_pass == form.get('new_pass2'):
        us.set_password(new_pass)
        return True, [gettext('Пароль обновлен')]
    return False, [gettext('Новые пароли не совпадают'), 'warning']

