from datetime import datetime, timedelta, timezone
import json
from flask import request, session, flash
from flask_login import current_user, login_user
from flask_babel import gettext

from ..app import login_manager, redis
from ..settings import LANGUAGES
from ..wallet.utils import create_new_wallet
from .models import db, User, UserInfo


@login_manager.user_loader
def find_user(user_id: int | None = None, email: str | None = None
              ) -> User | None:
    """Возвращает пользователя."""
    select = db.select(User)
    if user_id:
        select = select.filter_by(id=user_id)
    else:
        select = select.filter_by(email=email)
    return db.session.execute(select).scalar()


def create_new_user(email: str, password: str) -> User:
    """Создает нового пользователя."""
    new_user = User()
    new_user.email = email
    new_user.set_password(password)
    new_user.change_currency()
    new_user.change_locale(get_locale())

    db.session.add(new_user)
    db.session.flush()

    create_new_wallet(new_user)

    new_user.info = UserInfo()

    db.session.commit()
    return new_user


def register(form: dict) -> bool | None:
    """Обработка формы регистрации. Регистрация пользователя"""
    email = form.get('email')
    password = form.get('password')
    password2 = form.get('password2')

    if not (email and password and password2):
        flash(gettext('Заполните адрес электронной почты, '
                      'пароль и подтверждение пароля'), 'danger')

    elif find_user(email=email):
        flash(gettext('Данный почтовый ящик уже используется'), 'danger')

    elif password != password2:
        flash(gettext('Пароли не совпадают'), 'danger')

    else:
        create_new_user(email, password)
        flash(gettext('Вы зарегистрированы. Теперь войдите в систему'),
              'success')
        return True


def login(form: dict) -> bool:
    """Обработка формы входа. Вход пользовалетя"""
    email = form.get('email')
    password = form.get('password')
    redis_key = 'user_auth'

    # Поля не заполнены
    if not email or not password:
        flash(gettext('Введити адрес электронной почты и пароль'), 'danger')
        return False

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

            flash(gettext('Вход заблокирован'), 'danger')
            flash(gettext('Осталось %(m)s мин. %(s)s сек.', m=m, s=round(s)),
                  'danger')
            return False

    user = find_user(email=email)

    # Пользователь не найден
    if not user:
        flash(gettext('Неверный адрес электронной почты или пароль'), 'danger')
        return False

    # Проверка пройдена
    if user.check_password(password):
        login_user(user, form.get('remember-me', False))
        user.new_login()
        redis.hdel(redis_key, email)
        return True

    # Проверка не пройдена
    flash(gettext('Неверный адрес электронной почты или пароль'), 'danger')
    login_attempts.setdefault('count', 0)
    login_attempts['count'] += 1
    if login_attempts['count'] >= 5:
        next_try = datetime.now(timezone.utc) + timedelta(minutes=10)
        login_attempts['next_try_time'] = str(next_try)
        flash(gettext('Вход заблокирован на 10 минут'), 'danger')

    redis.hset(redis_key, email, json.dumps(login_attempts))


def get_demo_user() -> User | None:
    return db.session.execute(db.select(User).filter_by(type='demo')).scalar()


def get_locale() -> str:
    u = current_user
    if u.is_authenticated and u.type != 'demo' and u.locale:
        return u.locale
    locale = (session.get('locale')
              or request.accept_languages.best_match(LANGUAGES.keys()))
    return locale if locale else 'en'



def get_currency() -> str:
    u = current_user
    if u.is_authenticated and u.type != 'demo' and u.currency:
        return u.currency
    return session.get('currency', 'usd')


def get_timezone() -> str | None:
    if current_user.is_authenticated:
        return current_user.timezone
