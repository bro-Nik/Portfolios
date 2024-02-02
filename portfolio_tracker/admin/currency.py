from datetime import datetime, timedelta
import time

from flask import current_app

from ..app import db, redis
from ..wraps import logging
from ..general_functions import redis_decode, remove_prefix
from ..portfolio.models import PriceHistory
from .utils import get_tickers, request_json, task_log, \
    find_ticker_in_base, Market

MARKET: Market = 'currency'
BASE_URL: str = 'http://api.currencylayer.com/'
PRICE_UPDATE_KEY: str = 'update_currency'


def get_data(url: str) -> dict | None:
    attempts: int = 5  # Допустимое количество попыток
    minute_calls: int | None = 5  # Допустимое количество вызовов в минуту
    connector = '&' if '?' in url else '?'
    api_key: str = current_app.config['API_KEY_CURRENCYLAYER']
    url += f"{connector}access_key={api_key}"

    while attempts > 0:
        attempts -= 1

        # Задержка, если ограничено количество вызовов в минуту
        if minute_calls:
            time.sleep(60 / minute_calls)

        data = request_json(url, MARKET)
        if data and not data.get('error'):
            return data

        task_log(f'Осталось попыток: {attempts})', MARKET)
        current_app.logger.warning(f'Неудача (еще попыток: {attempts})',
                                   exc_info=True)


@logging
def load_prices() -> None:
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


@logging
def load_tickers() -> None:
    task_log('Загрузка тикеров - Старт', MARKET)

    # Получение данных
    url = f'{BASE_URL}list'
    data = get_data(url)
    if not data or not isinstance(data.get('currencies'), dict):
        return None

    # Сохранение данных
    tickers = get_tickers(MARKET)
    data = data['currencies']

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


@logging
def load_history() -> None:
    task_log('Загрузка истории - Старт', MARKET)

    date = datetime.now().date()
    tickers = get_tickers(MARKET)
    attempts: int = 5  # Количество запросов

    while attempts > 0:

        # Поиск даты для которой нет истории
        date -= timedelta(days=1)
        history = db.session.execute(db.select(PriceHistory)
                                     .filter_by(date=date)).scalar()
        if history:
            continue

        # Получение данных
        attempts -= 1
        url = f'{BASE_URL}historical?date='
        data = get_data(f'{url}{date}')

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
