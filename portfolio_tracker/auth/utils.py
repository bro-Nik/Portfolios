"""Логика авторизации"""

from datetime import datetime

from portfolio_tracker.app import db, login_manager
from portfolio_tracker.models import User, UserInfo


def find_user(email: str) -> User | None:
    """Принимает email, находит и возвращает пользователя."""
    return db.session.execute(db.select(User).filter_by(email=email)).scalar()


@login_manager.user_loader
def load_user(user_id: int) -> User | None:
    """Принимает ID и возвращает пользователя."""
    user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar()
    if user.info:
        user.info.last_visit = datetime.utcnow()
        db.session.commit()

    return user


def create_new_user(email: str, password: str) -> User:
    """Создает нового пользователя."""
    new_user = User(email=email)
    new_user.set_password(password)
    new_user.change_currency()
    new_user.change_locale()
    new_user.create_first_wallet()

    new_user.info = UserInfo()

    db.session.add(new_user)
    db.session.commit()
    return new_user
