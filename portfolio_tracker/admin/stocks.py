import time
from datetime import datetime, timedelta

from flask import current_app

from ..app import db, redis
from ..wraps import logging
from ..general_functions import redis_decode
from .utils import get_tickers, load_image, remove_prefix, request_json, \
    task_log, find_ticker_in_base, Market

MARKET: Market = 'crypto'
BASE_URL: str = 'https://api.polygon.io/'
PRICE_UPDATE_KEY: str = 'update_stocks'


def get_data(url):
    attempts: int = 5  # Допустимое количество попыток
    minute_calls: int | None = 5  # Допустимое количество вызовов в минуту
    connector = '&' if '?' in url else '?'
    api_key: str = current_app.config['API_KEY_POLYGON']
    url += f"{connector}apiKey={api_key}"

    while attempts > 0:
        attempts -= 1

        # Задержка, если ограничено количество вызовов в минуту
        if minute_calls:
            time.sleep(60 / minute_calls)

        data = request_json(url, MARKET)

        if data and data.get('results'):
            return data['results']

        task_log(f'Осталось попыток: {attempts})', MARKET)
        current_app.logger.warning(f'Неудача (еще попыток: {attempts})',
                                   exc_info=True)


@logging
def load_prices() -> None:
    date = datetime.now().date()

    # Обновление один раз в день
    if redis_decode(PRICE_UPDATE_KEY) == str(date):
        return None

    task_log('Загрузка цен - Старт', MARKET)

    # Получение данных
    max_attempts = 30
    data = None

    while not data or max_attempts > 0:
        max_attempts -= 1

        # Вчерашняя цена закрытия (т.к. бесплатно) или более поздняя
        date -= timedelta(days=1)
        url = f'{BASE_URL}v2/aggs/grouped/locale/us/market/stocks/{date}'
        data = get_data(url)

    if not data:
        return None

    # Сохранение данных
    for ticker in get_tickers(MARKET):
        ticker_in_data = data.get(remove_prefix(ticker.id, MARKET))
        if ticker_in_data:
            price = ticker_in_data['c']
            ticker.price = price

    db.session.commit()
    redis.set(PRICE_UPDATE_KEY, str(datetime.now().date()))

    task_log('Загрузка цен - Конец', MARKET)


@logging
def load_tickers() -> None:
    task_log('Загрузка тикеров - Старт', MARKET)

    tickers = get_tickers(MARKET)

    # Пакетная загрузка
    url = f'{BASE_URL}v3/reference/tickers?market=stocks&limit=1000'
    while url:
        # Получение данных
        data = get_data(url)
        if not data:
            break

        # Сохранение данных
        for stock in data:

            # Поиск или добавление нового тикера
            external_id = stock['ticker']
            ticker = find_ticker_in_base(external_id, tickers, MARKET, True)
            if not ticker:
                continue

            # Обновление информации
            ticker.name = stock['name']
            ticker.symbol = stock['ticker']

        db.session.commit()

        # Следующий URL
        url = data.get('next_url')

    redis.delete(PRICE_UPDATE_KEY)
    task_log('Загрузка тикеров - Конец', MARKET)


@logging
def load_images() -> None:
    task_log('Загрузка картинок - Старт', MARKET)

    tickers = get_tickers(MARKET, without_image=True)

    for ticker in tickers:
        ticker_id = remove_prefix(ticker.id, MARKET)
        url = f'{BASE_URL}v3/reference/tickers/{ticker_id}'

        try:
            data = get_data(url)
        except ValueError:
            continue

        if data and data.get('branding') and data['branding'].get('icon_url'):
            image_url = f"{data['branding']['icon_url']}"
            ticker.image = load_image(image_url, MARKET, ticker_id)
            db.session.commit()

    task_log('Загрузка картинок - Конец', MARKET)
