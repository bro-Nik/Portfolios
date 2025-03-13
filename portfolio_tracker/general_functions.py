import json
import pickle
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Literal, TypeAlias

from babel.dates import format_date
from flask import current_app, flash
from flask_login import current_user

from .app import redis, db


Market: TypeAlias = Literal['crypto', 'stocks', 'currency']
MARKETS: tuple[Market, ...] = ('crypto', 'stocks', 'currency')


def find_by_attr(iterable: Iterable, attr: str, attr_value: str | int | None):
    if not (iterable and attr_value):
        return

    # Если тип отличается - пробуем привести к нужному
    type_ = type(getattr(iterable[0], attr))
    if not isinstance(attr_value, type_):
        try:
            attr_value = type_(attr_value)
        except ValueError:
            return

    # Поиск совпадения
    for item in iterable:
        if getattr(item, attr) == attr_value:
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


def _json_to_dict(data_str: bytes) -> Dict[str, Any]:
    try:
        data = json.loads(data_str)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def actions_on_objects(data_str: bytes,
                       get_by_id: Callable[[List[int]], List[Any]]) -> None:
    data = _json_to_dict(data_str)
    ids = data.get('ids', [])
    action = data.get('action', '')

    if ids and action and get_by_id:
        # items = get_by_id(ids)
        # for item in items:
        for item_id in ids:
            item = get_by_id(item_id)
            method = getattr(item.service, action, None)
            if callable(method):
                method()

        db.session.commit()


def get_prefix(market: Market) -> str:
    return current_app.config[f'{market.upper()}_PREFIX']


def add_prefix(ticker_id: str, market: Market) -> str:
    return (get_prefix(market) + ticker_id).lower()


def remove_prefix(ticker_id: str, market: Market) -> str:
    prefix = get_prefix(market)
    if ticker_id.startswith(prefix):
        ticker_id = ticker_id[len(prefix):]

    return ticker_id


def print_flash_messages(messages):
    if messages:
        if isinstance(messages[0], list):
            for message in messages:
                print_flash_messages(message)

        else:
            flash(messages[0], messages[1] if len(messages) > 1 else '')
