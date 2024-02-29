from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING

from flask import current_app

from ..app import db, celery
from ..general_functions import Market, remove_prefix
from .integrations import task_logging
from .integrations_api import ApiIntegration, ApiName
from .utils import alerts_update, create_new_ticker, get_tickers, \
    load_image, find_ticker_in_list

if TYPE_CHECKING:
    import requests


API_NAME: ApiName = 'crypto'
MARKET: Market = 'crypto'
BASE_URL: str = 'https://api.coingecko.com/api/v3/'


class Api(ApiIntegration):
    def minute_limit_trigger(self, response: requests.models.Response
                             ) -> int | None:
        if response.status_code == 429:
            return int(response.headers.get('Retry-After', 120))

    def monthly_limit_trigger(self, response: requests.models.Response
                              ) -> bool:
        if response.status_code:
            pass
        return False

    def response_processing(self, response: requests.models.Response | None,
                            task_name) -> dict | None:
        if response:
            # Ответ с данными
            if response.status_code == 200:
                return response.json()

            # Ошибки
            m = f'Ошибка, Код: {response.status_code}, url: {response.url}'
            self.logs.set('warning', m, task_name)
            current_app.logger.warning(m, exc_info=True)


@celery.task(bind=True, name='crypto_load_prices', max_retries=None)
@task_logging
def crypto_load_prices(self) -> None:

    api = Api(API_NAME)
    tickers = get_tickers(MARKET)
    url = f'{BASE_URL}simple/price?vs_currencies=usd&ids='
    not_updated_ids = []

    while tickers:

        # Разбиение запроса до допустимой длины
        tickers_to_do = []
        ids = ''
        while (tickers and
               len(f'{url}{ids},{remove_prefix(tickers[0].id, MARKET)}') < 2048):
            ids += ',' + remove_prefix(tickers[0].id, MARKET)
            tickers_to_do.append(tickers.pop(0))

        # Получение данных
        response = api.request(lambda key: f'{url}/{ids}&{key}')
        data = api.response_processing(response, self.name)
        if not data:
            api.logs.set('error', 'Нет данных', self.name)
            return

        # Сохранение данных
        for ticker in tickers_to_do:
            external_id = remove_prefix(ticker.id, MARKET)
            ticker_in_data = data.get(external_id)
            if ticker_in_data:
                price = ticker_in_data.get('usd', 0)
                ticker.price = price
            else:
                # Добавление в словарь необновленных
                not_updated_ids.append(ticker.id)

        db.session.commit()
        api.logs.set('info', f'Осталось: {len(tickers)}', self.name)

    # Обновить уведомления
    alerts_update(MARKET)

    # События
    api.events.update(not_updated_ids, 'not_updated_prices')

    # Инфо
    api.info.set('Цены обновлены', datetime.now())


@celery.task(bind=True, name='crypto_load_tickers', max_retries=None)
@task_logging
def crypto_load_tickers(self) -> None:

    api = Api(API_NAME)
    tickers = get_tickers(MARKET)
    new_ids = []
    not_found_ids = [ticker.id for ticker in tickers]
    page = 1
    url = f'{BASE_URL}coins/markets?vs_currency=usd&per_page=250&page='

    while True:
        api.logs.set('info', f'Страница: {page}', self.name)

        # Получение данных
        response = api.request(lambda key: f'{url}{page}&{key}')
        data = api.response_processing(response, self.name)
        if not data:
            break

        # Сохранение данных
        for coin in data:

            # Внешний ID
            external_id = coin['id']
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

            # Добавление иконки
            image_url = coin.get('image')
            if not ticker.image and image_url:
                ticker.image = load_image(image_url, MARKET, ticker.id, api)

            # Обновление информации
            ticker.market_cap_rank = coin.get('market_cap_rank')
            ticker.name = coin.get('name')
            ticker.symbol = coin.get('symbol')

        db.session.commit()

        # Следующая страница
        page += 1

    # События
    api.events.update(new_ids, 'new_tickers', False)
    api.events.update(not_found_ids, 'not_found_tickers')

    # Инфо
    api.info.set('Тикеры обновлены', datetime.now())
