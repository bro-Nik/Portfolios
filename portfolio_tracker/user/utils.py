import time
from flask import current_app, request, session
from flask_login import current_user
from datetime import datetime, timedelta

from portfolio_tracker.app import db
from portfolio_tracker.settings import LANGUAGES
# from portfolio_tracker.models import User


def get_demo_user():
    from portfolio_tracker.models import User
    return db.session.execute(db.select(User).filter_by(type='demo')).scalar()


def from_user_datetime(date):
    if type(date) is str:
        date = datetime.strptime(date, '%Y-%m-%dT%H:%M')
    return date + timedelta(seconds=time.timezone)


def get_locale():
    if current_app.testing:
        return 'ru'

    u = current_user
    if u.is_authenticated and u.type != 'demo' and u.locale:
        return u.locale
    return session.get('locale') or request.accept_languages.best_match(LANGUAGES.keys())


def get_currency():
    u = current_user
    if u.is_authenticated and u.type != 'demo' and u.currency:
        return u.currency
    return session.get('currency', 'usd')


def get_timezone():
    if current_app.testing:
        return None

    if current_user.is_authenticated:
        return current_user.timezone
