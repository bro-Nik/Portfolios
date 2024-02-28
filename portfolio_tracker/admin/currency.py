from __future__ import annotations
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from flask import current_app

from ..app import db, celery
from ..general_functions import Market, remove_prefix
from ..portfolio.models import PriceHistory
from .api_integration import ApiIntegration, task_logging, ApiName
from .utils import create_new_ticker, get_tickers, find_ticker_in_list

if TYPE_CHECKING:
    import requests


API_NAME: ApiName = 'currency'
MARKET: Market = 'currency'
BASE_URL: str = 'http://api.currencylayer.com/'


class Api(ApiIntegration):
    def minute_limit_trigger(self, response: requests.models.Response
                             ) -> int | None:
        return

    def monthly_limit_trigger(self, response: requests.models.Response
                              ) -> bool:
        try:
            e = response.json()['error']
            return e['code'] == 104 and 'Your monthly usage limit' in e['info']
        except:
            return False

    def response_processing(self, response: requests.models.Response | None,
                            task_name, item: str) -> dict | None:
        if not response:
            return

        if response.status_code == 200:
            data = response.json()

            # Ответ с данными
            if data.get('success') and data.get(item):
                return data[item]

            # Ответ с ошибкой
            if data.get('error'):
                self.logs.set('warning', data['error'], task_name)

            # Ответ без данных
            self.logs.set('warning', f'Нет данных. {data}', task_name)

        else:
            # Остальные ошибки
            m = f'Ошибка, Код: {response.status_code}, url: {response.url}'
            self.logs.set('warning', m, task_name)
            current_app.logger.warning(m, exc_info=True)


@celery.task(bind=True, name='currency_load_prices', max_retries=None)
@task_logging
def currency_load_prices(self) -> None:

    api = Api(API_NAME)
    not_updated_ids = []

    # Получение данных
    response = api.request(lambda key: f'{BASE_URL}live?{key}')
    data = api.response_processing(response, self.name, 'quotes')
    if not data:
        return

    # Сохранение данных
    for ticker in get_tickers(MARKET):
        external_id = f'USD{remove_prefix(ticker.id, MARKET)}'.upper()
        price = data.get(external_id)
        if price:
            # Обновление цены к USD
            ticker.price = 1 / price
        else:
            # Добавление в список необновленных
            not_updated_ids.append(ticker.id)
    db.session.commit()

    # События
    api.events.update(not_updated_ids, 'not_updated_prices')

    # Инфо
    api.info.set('Цены обновлены', datetime.now())


@celery.task(bind=True, name='currency_load_tickers', max_retries=None)
@task_logging
def currency_load_tickers(self) -> None:

    api = Api(API_NAME)
    tickers = get_tickers(MARKET)
    new_ids = []
    not_found_ids = [ticker.id for ticker in tickers]

    # Получение данных
    response = api.request(lambda key: f'{BASE_URL}list?{key}')
    data = api.response_processing(response, self.name, 'currencies')
    if not data:
        return

    # Сохранение данных
    for external_id in data:

        # Внешний ID
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
        ticker.name = data[external_id]
        ticker.symbol = external_id
        ticker.stable = True

    db.session.commit()

    # События
    api.events.update(new_ids, 'new_tickers', False)
    api.events.update(not_found_ids, 'not_found_tickers')

    # Инфо
    api.info.set('Тикеры обновлены', datetime.now())


@celery.task(bind=True, name='currency_load_history')
@task_logging
def currency_load_history(self) -> None:

    api = Api(API_NAME)
    tickers = get_tickers(MARKET)
    date = datetime.now().date()
    attempts: int = 5  # Количество запросов
    url = f'{BASE_URL}historical?date='

    while attempts > 0:

        # Поиск даты для которой нет истории
        date -= timedelta(days=1)
        history = db.session.execute(db.select(PriceHistory)
                                     .filter_by(date=date)).scalar()
        if history:
            continue

        # Получение данных
        attempts -= 1

        response = api.request(lambda key: f'{url}{date}&{key}')
        data = api.response_processing(response, self.name, 'quotes')
        if not data:
            return

        # Сохранение данных
        for currency in data:

            # Поиск тикера
            external_id = currency[len('USD'):]
            ticker = find_ticker_in_list(external_id, tickers, MARKET)

            price = data[currency]
            if ticker and price:
                ticker.set_price(date, 1 / price)

        db.session.commit()
        api.logs.set('info', f'Получены цены на {date}', self.name)
