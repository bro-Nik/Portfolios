from __future__ import annotations
from typing import TYPE_CHECKING

from flask import request, session
from flask_login import current_user

from portfolio_tracker.settings import LANGUAGES

if TYPE_CHECKING:
    from ..models import User


def get_locale(user: User = current_user) -> str:  # type: ignore
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

    if user.is_authenticated and not user.is_demo and user.locale:
        return user.locale
    return (session.get('locale')
            or request.accept_languages.best_match(LANGUAGES.keys()) or 'en')


def get_currency(user: User = current_user) -> str:   # type: ignore
    """Получает валюту пользователя.

    Если пользователь аутентифицирован, не является демо-пользователем и у него задана валюта,
    возвращает её. В противном случае возвращает валюту из сессии или по умолчанию 'usd'.

    Аргументы:
        user (User): Пользователь, для которого необходимо получить валюту.
                     По умолчанию используется текущий пользователь.

    Возвращает:
        str: Строка, представляющая валюту пользователя.

    """

    if user.is_authenticated and not user.is_demo and user.currency:
        return user.currency
    return session.get('currency', 'usd')


def get_timezone(user: User = current_user) -> str | None:   # type: ignore
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

    if user.is_authenticated:
        return current_user.timezone
