from __future__ import annotations
import json
import pickle
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Iterable, Literal, TypeAlias

from babel.dates import format_date
from flask import current_app
from flask_login import current_user

from .app import redis


Market: TypeAlias = Literal['crypto', 'stocks', 'currency']
MARKETS: tuple[Market, ...] = ('crypto', 'stocks', 'currency')


def find_by_attr(iterable: Iterable, attr: str, search: str | int | None):
    # Если iterable или search пустое - выход
    if not iterable or not search:
        return

    # Если тип отличается - пробуем привести к нужному
    type_ = type(getattr(iterable[0], attr))
    if not isinstance(search, type_):
        try:
            search = type_(search)
        except ValueError:
            return

    # Поиск совпадения
    for item in iterable:
        if getattr(item, attr) == search:
            return item


def redis_decode(key: str, default: Any = '') -> Any:
    result = redis.get(key)
    return pickle.loads(result) if result else default


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
            result = f'{int(delta_time.total_seconds() / 60)} мин. назад'

        else:
            result = f'{int(delta_time.total_seconds() / 3600)} ч. назад'

    elif 0 < (date - datetime.date(update_date)).days < 2:
        result = 'вчера'

    elif 2 <= (date - datetime.date(update_date)).days < 10:
        result = f'{int((date - datetime.date(update_date)).days)} д. назад'

    else:
        result = format_date(update_date, locale=current_user.locale.upper())
    return result


def actions_in(data_str: bytes, function: Callable, **kwargs) -> None:
    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        data = {}

    if isinstance(data, dict):
        ids = data.get('ids', [])
        action = data.get('action', '')

        for item_id in ids:
            item = function(item_id, **kwargs)
            if item and hasattr(item, action):
                getattr(item, action)()


def get_prefix(market: Market) -> str:
    return current_app.config[f'{market.upper()}_PREFIX']


def add_prefix(ticker_id: str, market: Market) -> str:
    return (get_prefix(market) + ticker_id).lower()


def remove_prefix(ticker_id: Ticker.id, market: Market) -> str:
    prefix = get_prefix(market)
    if ticker_id.startswith(prefix):
        ticker_id = ticker_id[len(prefix):]

    return ticker_id
