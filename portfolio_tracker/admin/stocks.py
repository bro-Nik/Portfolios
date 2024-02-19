from datetime import datetime, timedelta, timezone

import requests

from ..app import db, celery
from ..general_functions import Market, remove_prefix
from .utils import alerts_update, api_info, create_new_ticker, get_api, \
    get_data, get_tickers, load_image, response_json, api_logging, \
    find_ticker_in_base, ApiName, task_logging, api_event


API_NAME: ApiName = 'stocks'
MARKET: Market = 'stocks'
BASE_URL: str = 'https://api.polygon.io/'


def check_response(response: requests.models.Response | None,
                   task_name: str, item: str = '') -> dict:
    if response:
        data = response_json(response)
        if data:
            return data[item] if item else data

        api_logging.set('error', 'Нет данных', API_NAME, task_name)
    return {}


@celery.task(bind=True, name='stocks_load_prices', max_retries=None)
@task_logging
def stocks_load_prices(self, retry_after) -> None:

    api = get_api(API_NAME)
    tickers = get_tickers(MARKET)
    not_updated_ids = [ticker.id for ticker in tickers]
    max_attempts = 30
    url = f'{BASE_URL}v2/aggs/grouped/locale/us/market/stocks/'
    data = None

    # Если меньше полудня - запрос на предыдущий день
    date = datetime.now().date()
    if datetime.now(timezone.utc).hour < 12:
        date -= timedelta(days=1)

    # Получение данных
    while not data and max_attempts > 0:
        max_attempts -= 1

        # Вчерашняя цена закрытия (т.к. бесплатно) или более поздняя
        date -= timedelta(days=1)

        api_logging.set('info', f'Попытка запроса на {date}', API_NAME, self.name)
        data = get_data(lambda key: f'{url}{date}?{key}', api)
        data = check_response(data, self.name, 'results')

    if not data:
        return

    # Сохранение данных
    for item in data:
        ticker = find_ticker_in_base(item['T'], tickers, MARKET)
        if ticker:
            ticker.price = item['c']
            # Исключение из списка необновленных
            if ticker.id in not_updated_ids:
                not_updated_ids.remove(ticker.id)

    db.session.commit()

    # Обновить уведомления
    alerts_update(MARKET)

    # События
    api_event.update(API_NAME, not_updated_ids, 'not_updated_prices')

    # Инфо
    api_info.set('Цены обновлены', datetime.now(), API_NAME)

    # Следующий запуск
    if retry_after:
        self.default_retry_delay = retry_after
        self.retry()


@celery.task(bind=True, name='stocks_load_tickers', max_retries=None)
@task_logging
def stocks_load_tickers(self, retry_after) -> None:

    api = get_api(API_NAME)
    tickers = get_tickers(MARKET)
    new_ids = []
    not_found_ids = [ticker.id for ticker in tickers]
    url = f'{BASE_URL}v3/reference/tickers?market=stocks&limit=1000'

    # Пакетная загрузка
    while url:
        # Получение данных
        data = get_data(lambda key: f'{url}&{key}', api)
        data = check_response(data, self.name)
        stocks = data.get('results')
        if not stocks:
            break

        # Сохранение данных
        for stock in stocks:

            # Внешний ID
            external_id = stock['ticker']
            if not external_id:
                continue

            # Поиск тикера
            ticker = find_ticker_in_base(external_id, tickers, MARKET)
            # Или добавление нового тикера
            if not ticker:
                ticker = create_new_ticker(external_id, MARKET)
                tickers.append(ticker)
                new_ids.append(ticker.id)

            # Исключение из списка ненайденных
            if ticker.id in not_found_ids:
                not_found_ids.remove(ticker.id)

            # Обновление информации
            ticker.name = stock['name']
            ticker.symbol = stock['ticker']

        db.session.commit()

        # Следующий URL
        url = data.get('next_url')
        if url:
            api_logging.set('info', 'Получен следующий url', API_NAME, self.name)

    # События
    api_event.update(API_NAME, new_ids, 'new_tickers', False)
    api_event.update(API_NAME, not_found_ids, 'not_found_tickers')

    # Инфо
    api_info.set('Тикеры обновлены', datetime.now(), API_NAME)

    # Следующий запуск
    if retry_after:
        self.default_retry_delay = retry_after
        self.retry()


@celery.task(bind=True, name='stocks_load_images')
@task_logging
def stocks_load_images(self, retry_after) -> None:

    api = get_api(API_NAME)
    tickers = get_tickers(MARKET, without_image=True)
    url = f'{BASE_URL}v3/reference/tickers/'
    loaded_ids = []

    while tickers:
        ticker = tickers.pop(0)
        ticker_id = remove_prefix(ticker.id, MARKET)

        # Получение данных
        t_id = ticker_id.upper()
        data = get_data(lambda key: f'{url}{t_id}?{key}', api)
        data = check_response(data, self.name, 'results')
        if not (data.get('branding') and data['branding'].get('icon_url')):
            continue

        # Загрузка иконки
        image_url = f"{data['branding']['icon_url']}"
        ticker.image = load_image(image_url, MARKET, ticker_id, API_NAME)
        db.session.commit()
        api_logging.set('info', f'Осталось {len(tickers)}', API_NAME, self.name)
        # Добавление в список обновленных
        loaded_ids.append(ticker.id)

    # События
    api_event.update(API_NAME, loaded_ids, 'updated_images', False)

    # Следующий запуск
    if retry_after:
        self.default_retry_delay = retry_after
        self.retry()
