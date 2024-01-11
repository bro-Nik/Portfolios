from datetime import datetime, timedelta
import time
import requests

from flask import current_app

from portfolio_tracker.general_functions import redis_decode
from portfolio_tracker.models import PriceHistory, db
from portfolio_tracker.app import redis
from portfolio_tracker.admin.utils import get_tickers, remove_prefix, \
    task_log, find_ticker_in_base


MARKET = 'currency'
BASE_URL = 'http://api.currencylayer.com/'
PRICE_UPDATE_KEY = 'update_currency'


def get_data(url):
    max_attempts = 5  # Допустимое количество попыток
    minute_calls = 5  # Допустимое количество вызовов в минуту
    connector = '&' if '?' in url else '?'
    url += f"{connector}access_key={current_app.config['API_KEY_CURRENCYLAYER']}"

    while max_attempts > 0:
        max_attempts -= 1

        # Задержка, если ограничено количество вызовов в минуту
        if minute_calls:
            time.sleep(60 / minute_calls)

        try:
            response = requests.get(url)
            data = response.json()
            if not data.get('error'):
                task_log('Удачный запрос', MARKET)
                return data

        except Exception as error:
            task_log(f'Неудачный запрос (осталось {max_attempts} попыток) - {error}', MARKET)


def load_prices():
    # Обновление один раз в день
    if redis_decode(PRICE_UPDATE_KEY) == str(datetime.now().date()):
        return None

    task_log('Загрузка цен - Старт', MARKET)

    # Получение данных
    url = f'{BASE_URL}live'
    data = get_data(url)
    if not data:
        return None

    # Сохранение данных
    data = data['quotes']

    for ticker in get_tickers(MARKET):
        price = data.get(remove_prefix(ticker.id, MARKET))
        if price:
            ticker.price = 1 / price

    db.session.commit()
    redis.set(PRICE_UPDATE_KEY, str(datetime.now().date()))

    task_log('Загрузка цен - Конец', MARKET)


def load_tickers():
    task_log('Загрузка тикеров - Старт', MARKET)

    # Получение данных
    url = f'{BASE_URL}list'
    data = get_data(url)
    if not data or not data.get('currencies'):
        return None

    # Сохранение данных
    tickers = list(get_tickers(MARKET))
    data = data.get('currencies')

    for currency in data:

        # Поиск или добавление нового тикера
        external_id = currency
        ticker = find_ticker_in_base(external_id, tickers, MARKET, True)
        if not ticker:
            continue

        # Обновление информации
        ticker.name = data[currency]
        ticker.symbol = currency
        ticker.stable = True

    db.session.commit()
    redis.delete(PRICE_UPDATE_KEY)

    task_log('Загрузка тикеров - Конец', MARKET)


def load_history():
    task_log('Загрузка истории - Старт', MARKET)

    date = datetime.now().date()
    tickers = tuple(get_tickers(MARKET))

    # ToDO потом убрать
    n = 0
    while n <= 3:

        # Поиск даты для которой нет истории
        date -= timedelta(days=1)
        history = db.session.execute(db.select(PriceHistory)
                                     .filter_by(date=date)).scalar()
        if history:
            continue

        # Получение данных
        url = f'{BASE_URL}historical?date='
        data = get_data(f'{url}{date}')
        n += 1

        if not data or not data.get('quotes'):
            return None

        # Сохранение данных
        data = data['quotes']

        for currency in data:

            # Поиск тикера
            external_id = currency[len('USD'):]
            ticker = find_ticker_in_base(external_id, tickers, MARKET)

            price = data[currency]
            if ticker and price:
                ticker.set_price(date, 1 / price)

        db.session.commit()
    task_log('Загрузка истории - Конец', MARKET)
