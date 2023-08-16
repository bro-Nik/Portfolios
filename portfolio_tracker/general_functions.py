import pickle
from datetime import datetime, timedelta
from portfolio_tracker.app import redis


def dict_get_or_other(dict, key, default=None):
    return dict.get(key) if dict and dict.get(key) else default


def float_or_other(number, default=0):
    return float(number) if number else default

def redis_decode_or_other(key, default=''):
    key = redis.get(key)
    if not key:
        return default
    return key.decode()

def price_list_def():
    ''' Общая функция сбора цен '''
    crypto_redis = redis.get('price_list_crypto')
    price_list_crypto = pickle.loads(crypto_redis) if crypto_redis else {}
    stocks_redis = redis.get('price_list_stocks')
    price_list_stocks = pickle.loads(stocks_redis) if stocks_redis else {}

    return price_list_crypto | price_list_stocks


def when_updated_def(when_updated, default=''):
    ''' Возвращает сколько прошло от входящей даты '''
    if not when_updated:
        return default
    if type(when_updated) == str:
        try:
            when_updated = datetime.strptime(
                when_updated, '%Y-%m-%d %H:%M:%S.%f')
        except:
            when_updated = datetime.strptime(
                when_updated + ' 20:00:00.000000', '%Y-%m-%d %H:%M:%S.%f')

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
        result = str(datetime.strftime(when_updated, '%Y-%m-%d %H:%M'))
    return result