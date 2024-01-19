import time
from datetime import datetime, timedelta
from typing import Any, Iterable

from babel.dates import format_date
from flask_login import current_user

from .app import redis


def find_by_id(iterable: Iterable, search_id: int) -> Any:
    for item in iterable:
        if item.id == search_id:
            return item


def redis_decode(key: str, default: str = '') -> str:
    result = redis.get(key)
    return result.decode() if result else default


def from_user_datetime(date: datetime | str) -> datetime:
    if isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%dT%H:%M')
    return date + timedelta(seconds=time.timezone)


def when_updated(update_date: datetime | str, default: str = '') -> str:
    """ Возвращает сколько прошло от входящей даты """
    if not update_date:
        return default

    if isinstance(update_date, str):
        if len(update_date) < 14:
            update_date = datetime.strptime(f'{update_date} 00:00:00.000000',
                                            '%Y-%m-%d %H:%M:%S.%f')
        else:
            update_date = datetime.strptime(update_date,
                                            '%Y-%m-%d %H:%M:%S.%f')

    delta_time = datetime.now() - update_date
    date = datetime.now().date()

    if date == datetime.date(update_date):
        if delta_time.total_seconds() < 60:
            result = 'менее минуты'

        elif 60 <= delta_time.total_seconds() < 3600:
            result = f'{delta_time.total_seconds() / 60} мин.'

        else:
            result = f'{delta_time.total_seconds() / 3600} ч.'

    elif 0 < (date - datetime.date(update_date)).days < 2:
        result = 'вчера'

    elif 2 <= (date - datetime.date(update_date)).days < 10:
        result = f'{(date - datetime.date(update_date)).days} д. назад'

    else:
        result = format_date(update_date, locale=current_user.locale.upper())
    return result
