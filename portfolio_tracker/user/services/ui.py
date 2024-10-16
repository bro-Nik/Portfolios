from __future__ import annotations
from typing import TYPE_CHECKING

from flask import request, session
from flask_login import current_user

from portfolio_tracker.settings import LANGUAGES
from .user import UserService

if TYPE_CHECKING:
    from ..models import User


def get_locale(user: User = current_user) -> str:
    """Получает локаль пользователя.

    Если пользователь аутентифицирован, не является демо-пользователем и у него задана локаль,
    возвращает её. В противном случае возвращает локаль из сессии или лучшую подходящую локаль
    из заголовка Accept-Language. Если ничего не найдено, возвращает 'en'.

    Аргументы:
        user (User): Пользователь, для которого необходимо получить локаль.
                     По умолчанию используется текущий пользователь.

    Возвращает:
        str: Строка, представляющая локаль пользователя.

    """

    us = UserService(user)

    if us.is_authenticated() and not us.is_demo() and user.locale:
        return user.locale
    return (session.get('locale')
            or request.accept_languages.best_match(LANGUAGES.keys()) or 'en')


def get_currency(user: User = current_user) -> str:
    """Получает валюту пользователя.

    Если пользователь аутентифицирован, не является демо-пользователем и у него задана валюта,
    возвращает её. В противном случае возвращает валюту из сессии или по умолчанию 'usd'.

    Аргументы:
        user (User): Пользователь, для которого необходимо получить валюту.
                     По умолчанию используется текущий пользователь.

    Возвращает:
        str: Строка, представляющая валюту пользователя.

    """

    us = UserService(user)

    if us.is_authenticated() and not us.is_demo() and user.currency:
        return user.currency
    return session.get('currency', 'usd')


def get_timezone(user: User = current_user) -> str | None:
    """Получает часовой пояс пользователя.

    Если пользователь аутентифицирован, возвращает его часовой пояс.
    В противном случае возвращает None.

    Аргументы:
        user (User): Пользователь, для которого необходимо получить часовой пояс.
                     По умолчанию используется текущий пользователь.

    Возвращает:
        str: Строка, представляющая часовой пояс пользователя, или None,
             если пользователь не аутентифицирован.

    """

    us = UserService(user)

    if us.is_authenticated():
        return current_user.timezone
