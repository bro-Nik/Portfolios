import time
import pickle
from datetime import datetime, timedelta
from babel.dates import format_date
from flask import current_app, g
from flask_login import current_user
from portfolio_tracker.app import redis


def redis_decode(key, default=''):
    key = redis.get(key)
    if key:
        return key.decode()

    return default


def get_price_list(market=None):
    ''' Общая функция сбора цен '''
    def get_for(market):
        price_list_key = 'price_list_' + market
        price_list = redis.get(price_list_key)
        return pickle.loads(price_list) if price_list else {}

    if market:
        return get_for(market)

    price_list = getattr(g, 'price_list', None)
    if price_list is None:
        price_list = get_for('crypto') | get_for('stocks') | get_for('currency')
        # USD
        price_list[current_app.config['CURRENCY_PREFIX'] + 'usd'] = 1
        g.price_list = price_list

    return price_list


def get_price(ticker_id, default=0):
    return get_price_list().get(ticker_id, default)


def from_user_datetime(date: datetime | str) -> datetime:
    if isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%dT%H:%M')
    return date + timedelta(seconds=time.timezone)


def when_updated(when_updated, default=''):
    ''' Возвращает сколько прошло от входящей даты '''
    if not when_updated:
        return default

    if type(when_updated) == str:
        try:
            when_updated = datetime.strptime(
                when_updated, '%Y-%m-%d %H:%M:%S.%f')
        except:
            when_updated = datetime.strptime(
                when_updated + ' 00:00:00.000000', '%Y-%m-%d %H:%M:%S.%f')

    delta_time = datetime.now() - when_updated
    date = datetime.now().date()
    if date == datetime.date(when_updated):
        if delta_time.total_seconds() < 60:
            result = 'менее минуты'
        elif 60 <= delta_time.total_seconds() < 3600:
            result = str(int(delta_time.total_seconds() / 60)) + ' мин.'
        else:
            result = str(int(delta_time.total_seconds() / 3600)) + ' ч.'
    elif 0 < (date - datetime.date(when_updated)).days < 2:
        result = 'вчера'
    elif 2 <= (date - datetime.date(when_updated)).days < 10:
        result = str((date - datetime.date(when_updated)).days) + 'д. назад'
    else:
        result = format_date(when_updated, locale=current_user.locale.upper())
        # result = str(datetime.strftime(when_updated, '%Y-%m-%d %H:%M'))
    return result

