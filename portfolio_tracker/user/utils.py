from flask import current_app, request, session, flash
from flask_login import current_user, login_user
from flask_babel import gettext

from portfolio_tracker.app import login_manager
from portfolio_tracker.settings import LANGUAGES
from portfolio_tracker.models import db, User, UserInfo


def find_user(email: str) -> User | None:
    """Принимает email, находит и возвращает пользователя."""
    return db.session.execute(db.select(User).filter_by(email=email)).scalar()


@login_manager.user_loader
def load_user(user_id: int) -> User | None:
    """Принимает ID и возвращает пользователя."""
    return db.session.execute(db.select(User).filter_by(id=user_id)).scalar()


def create_new_user(email: str, password: str) -> User:
    """Создает нового пользователя."""
    new_user = User()
    new_user.email = email
    new_user.set_password(password)
    new_user.change_currency()
    new_user.change_locale()
    new_user.create_first_wallet()

    new_user.info = UserInfo()

    db.session.add(new_user)
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

    elif find_user(email):
        flash(gettext('Данный почтовый ящик уже используется'), 'danger')

    elif password != password2:
        flash(gettext('Пароли не совпадают'), 'danger')

    else:
        create_new_user(email, password)
        flash(gettext('Вы зарегистрированы. Теперь войдите в систему'),
              'success')
        return True


def login(form: dict) -> bool | None:
    """Обработка формы входа. Вход пользовалетя"""
    email = form.get('email')
    password = form.get('password')

    if not email or not password:
        flash(gettext('Введити адрес электронной почты и пароль'), 'danger')

    else:
        user = find_user(email)
        if user and user.check_password(password):
            login_user(user, form.get('remember-me', False))
            user.new_login()

            return True

        flash(gettext('Неверный адрес электронной почты или пароль'), 'danger')


def get_demo_user() -> User | None:
    return db.session.execute(db.select(User).filter_by(type='demo')).scalar()


def get_locale() -> str | None:
    if current_app.testing:
        return 'ru'

    u = current_user
    if u.is_authenticated and u.type != 'demo' and u.locale:
        return u.locale
    return (session.get('locale')
            or request.accept_languages.best_match(LANGUAGES.keys()))


def get_currency() -> str:
    u = current_user
    if u.is_authenticated and u.type != 'demo' and u.currency:
        return u.currency
    return session.get('currency', 'usd')


def get_timezone() -> str | None:
    if current_app.testing:
        return None

    if current_user.is_authenticated:
        return current_user.timezone
