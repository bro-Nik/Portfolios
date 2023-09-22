import pickle
from datetime import datetime
from portfolio_tracker.app import redis


def int_(number, default=0):
    try:
        return int(number)
    except:
        return default

def float_(number, default=0):
    try:
        return float(number)
    except:
        return default

def redis_decode_or_other(key, default=''):
    key = redis.get(key)
    if not key:
        return default
    return key.decode()


def get_price_list(market=''):
    ''' Общая функция сбора цен '''
    def get_price_list_market(market):
        price_list_key = 'price_list_' + market
        price_list = redis.get(price_list_key)
        return pickle.loads(price_list) if price_list else {}

    if market:
        return get_price_list_market(market)

    return {'crypto': get_price_list_market('crypto'),
            'stocks': get_price_list_market('stocks')}


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
        result = str(datetime.strftime(when_updated, '%Y-%m-%d %H:%M'))
    return result


