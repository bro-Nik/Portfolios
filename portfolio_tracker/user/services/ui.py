from __future__ import annotations
from typing import TYPE_CHECKING

from flask import request, session
from flask_login import current_user

from portfolio_tracker.settings import LANGUAGES
from .user import UserService

if TYPE_CHECKING:
    from ..models import User


def get_locale(user: User = current_user) -> str:
    us = UserService(user)

    if us.is_authenticated() and not us.is_demo() and user.locale:
        return user.locale
    return (session.get('locale')
            or request.accept_languages.best_match(LANGUAGES.keys()) or 'en')


def get_currency(user: User = current_user) -> str:
    us = UserService(user)

    if us.is_authenticated() and not us.is_demo() and user.currency:
        return user.currency
    return session.get('currency', 'usd')


def get_timezone(user: User = current_user) -> str | None:
    us = UserService(user)

    if us.is_authenticated():
        return current_user.timezone
