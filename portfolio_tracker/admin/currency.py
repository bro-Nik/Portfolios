from datetime import datetime, timedelta
import requests

from ..app import db, celery
from ..general_functions import Market, remove_prefix
from ..portfolio.models import PriceHistory
from .utils import api_info, create_new_ticker, get_api, get_tickers, \
    get_data, response_json, api_logging, find_ticker_in_base, ApiName, \
    task_logging, api_event


API_NAME: ApiName = 'currency'
MARKET: Market = 'currency'
BASE_URL: str = 'http://api.currencylayer.com/'


def check_response(response: requests.models.Response | None,
                   task_name: str, item: str) -> dict | None:
    if response:
        data = response_json(response)
        if data.get('success'):
            if item and data.get(item):
                return data[item]

            api_logging.set('error', 'Нет данных', API_NAME, task_name)

        if data.get('error'):
            api_logging.set('error', data['error'], API_NAME, task_name)


@celery.task(bind=True, name='currency_load_prices', max_retries=None)
@task_logging
def currency_load_prices(self) -> None:

    api = get_api(API_NAME)
    not_updated_ids = []

    # Получение данных
    data = get_data(lambda key: f'{BASE_URL}live?{key}', api)
    data = check_response(data, self.name, 'quotes')
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
    api_event.update(API_NAME, not_updated_ids, 'not_updated_prices')

    # Инфо
    api_info.set('Цены обновлены', datetime.now(), API_NAME)


@celery.task(bind=True, name='currency_load_tickers', max_retries=None)
@task_logging
def currency_load_tickers(self) -> None:

    api = get_api(API_NAME)
    tickers = get_tickers(MARKET)
    new_ids = []
    not_found_ids = [ticker.id for ticker in tickers]

    # Получение данных
    data = get_data(lambda key: f'{BASE_URL}list?{key}', api)
    data = check_response(data, self.name, 'currencies')
    if not data:
        return

    # Сохранение данных
    for external_id in data:

        # Внешний ID
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
        ticker.name = data[external_id]
        ticker.symbol = external_id
        ticker.stable = True

    db.session.commit()

    # События
    api_event.update(API_NAME, new_ids, 'new_tickers', False)
    api_event.update(API_NAME, not_found_ids, 'not_found_tickers')

    # Инфо
    api_info.set('Тикеры обновлены', datetime.now(), API_NAME)


@celery.task(bind=True, name='currency_load_history')
@task_logging
def currency_load_history(self) -> None:

    api = get_api(API_NAME)
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
        data = get_data(lambda key: f'{url}{date}&{key}', api)
        data = check_response(data, API_NAME, 'quotes')
        if not data:
            return

        # Сохранение данных
        for currency in data:

            # Поиск тикера
            external_id = currency[len('USD'):]
            ticker = find_ticker_in_base(external_id, tickers, MARKET)

            price = data[currency]
            if ticker and price:
                ticker.set_price(date, 1 / price)

        db.session.commit()
        api_logging.set('info', f'Получены цены на {date}', API_NAME, self.name)
