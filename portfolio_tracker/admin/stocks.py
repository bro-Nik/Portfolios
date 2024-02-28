from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from flask import current_app

from ..app import db, celery
from ..general_functions import Market, remove_prefix
from .api_integration import ApiIntegration, task_logging, ApiName
from .utils import alerts_update, create_new_ticker, get_tickers, \
    load_image, find_ticker_in_list

if TYPE_CHECKING:
    import requests


API_NAME: ApiName = 'stocks'
MARKET: Market = 'stocks'
BASE_URL: str = 'https://api.polygon.io/'


class Api(ApiIntegration):
    def minute_limit_trigger(self, response: requests.models.Response
                             ) -> int | None:
        return False

    def monthly_limit_trigger(self, response: requests.models.Response
                              ) -> bool:
        return False

    def response_processing(self, response: requests.models.Response | None
                            ) -> dict | None:
        if response:
            # Ответ с данными
            if response.status_code == 200:
                return response.json()

            # Ошибки
            m = f'Ошибка, Код: {response.status_code}, {response.url}'
            self.logs.set('warning', m)
            current_app.logger.warning(m, exc_info=True)


@celery.task(bind=True, name='stocks_load_prices', max_retries=None)
@task_logging
def stocks_load_prices(self) -> None:

    api = Api(API_NAME)
    tickers = get_tickers(MARKET)
    not_updated_ids = [ticker.id for ticker in tickers]
    max_attempts = 5
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

        api.logs.set('info', f'Попытка запроса на {date}', self.name)
        response = api.request(lambda key: f'{url}{date}?{key}')
        data = api.response_processing(response)
        # Ошибка
        if not data:
            return
        data = data.get('results')

    if not data:
        api.logs.set('error', 'Нет данных', self.name)
        return

    # Сохранение данных
    for item in data:
        ticker = find_ticker_in_list(item['T'], tickers, MARKET)
        if ticker:
            ticker.price = item['c']
            # Исключение из списка необновленных
            if ticker.id in not_updated_ids:
                not_updated_ids.remove(ticker.id)

    db.session.commit()

    # Обновить уведомления
    alerts_update(MARKET)

    # События
    api.events.update(not_updated_ids, 'not_updated_prices')

    # Инфо
    api.info.set('Цены обновлены', datetime.now())


@celery.task(bind=True, name='stocks_load_tickers', max_retries=None)
@task_logging
def stocks_load_tickers(self) -> None:

    api = Api(API_NAME)
    tickers = get_tickers(MARKET)
    new_ids = []
    not_found_ids = [ticker.id for ticker in tickers]
    url = f'{BASE_URL}v3/reference/tickers?market=stocks&limit=1000'

    # Пакетная загрузка
    while url:
        # Получение данных
        response = api.request(lambda key: f'{url}&{key}')
        data = api.response_processing(response)
        # Ошибка
        if not data:
            return

        stocks = data.get('results')
        if not stocks:
            api.logs.set('error', 'Нет данных', self.name)
            break

        # Сохранение данных
        for stock in stocks:

            # Внешний ID
            external_id = stock['ticker']
            if not external_id:
                continue

            # Поиск тикера
            ticker = find_ticker_in_list(external_id, tickers, MARKET)
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
            api.logs.set('info', 'Получен следующий url', self.name)

    # События
    api.events.update(new_ids, 'new_tickers', False)
    api.events.update(not_found_ids, 'not_found_tickers')

    # Инфо
    api.info.set('Тикеры обновлены', datetime.now())


@celery.task(bind=True, name='stocks_load_images')
@task_logging
def stocks_load_images(self) -> None:

    api = Api(API_NAME)
    tickers = get_tickers(MARKET, without_image=True)
    url = f'{BASE_URL}v3/reference/tickers/'
    loaded_ids = []

    while tickers:
        ticker = tickers.pop(0)
        ticker_id = remove_prefix(ticker.id, MARKET)

        # Получение данных
        t_id = ticker_id.upper()
        response = api.request(lambda key: f'{url}{t_id}?{key}')
        data = api.response_processing(response)
        data = data.get('results', {}) if data else {}
        if not (data.get('branding') and data['branding'].get('icon_url')):
            continue

        # Загрузка иконки
        image_url = f"{data['branding']['icon_url']}"
        ticker.image = load_image(image_url, MARKET, ticker_id, api)
        db.session.commit()
        api.logs.set('info', f'Осталось {len(tickers)}', API_NAME)
        # Добавление в список обновленных
        loaded_ids.append(ticker.id)

    # События
    api.events.update(loaded_ids, 'updated_images', False)
