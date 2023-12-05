from datetime import datetime

from flask import flash
from flask_babel import gettext
from flask_login import login_user
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, login_manager, User, UserInfo


def find_user(email: str) -> User | None:
    """Принимает email, находит и возвращает пользователя."""
    return db.session.execute(db.select(User).filter_by(email=email)).scalar()


@login_manager.user_loader
def load_user(user_id: int) -> User | None:
    """Принимает ID и возвращает пользователя."""
    user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar()
    if user and user.info:
        user.info.last_visit = datetime.utcnow()
        db.session.commit()

    return user


def create_new_user(email: str, password: str) -> User:
    """Создает нового пользователя."""
    new_user = User(email=email)
    set_password(new_user, password)
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
        if user and check_password(user, password):
            login_user(user, form.get('remember-me', False, type=bool))
            user.new_login()

            return True

        flash(gettext('Неверный адрес электронной почты или пароль'), 'danger')


def set_password(user: User, password: str) -> None:
    """Изменение пароля пользователя."""
    user.password = generate_password_hash(password)


def check_password(password: str, password2: str) -> bool:
    """Проверка пароля пользователя."""
    return check_password_hash(password, password2)
