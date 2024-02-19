from datetime import datetime

# from pycoingecko import CoinGeckoAPI

from ..app import db, celery
from ..general_functions import Market, remove_prefix
from .utils import alerts_update, api_info, \
    create_new_ticker, get_data, get_tickers, \
    response_json, api_logging, load_image, find_ticker_in_base, ApiName, \
    get_api, task_logging, api_event


API_NAME: ApiName = 'crypto'
MARKET: Market = 'crypto'
BASE_URL: str = 'https://api.coingecko.com/api/v3/'


@celery.task(bind=True, name='crypto_load_prices', max_retries=None)
@task_logging
def crypto_load_prices(self, retry_after) -> None:

    api = get_api(API_NAME)
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
        data = get_data(lambda key: f'{url}/{ids}&{key}', api)
        data = response_json(data)
        if not data:
            api_logging.set('error', 'Нет данных', API_NAME, self.name)
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
        api_logging.set('info', f'Осталось: {len(tickers)}', API_NAME, self.name)

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


@celery.task(bind=True, name='crypto_load_tickers', max_retries=None)
@task_logging
def crypto_load_tickers(self, retry_after) -> None:

    api = get_api(API_NAME)
    tickers = get_tickers(MARKET)
    new_ids = []
    not_found_ids = [ticker.id for ticker in tickers]
    page = 1
    url = f'{BASE_URL}coins/markets?vs_currency=usd&per_page=250&page='

    while True:
        api_logging.set('info', f'Страница: {page}', API_NAME, self.name)

        # Получение данных
        data = get_data(lambda key: f'{url}{page}&{key}', api)
        data = response_json(data)
        if not data:
            break

        # Сохранение данных
        for coin in data:

            # Внешний ID
            external_id = coin['id']
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

            # Добавление иконки
            image_url = coin.get('image')
            if not ticker.image and image_url:
                ticker.image = load_image(image_url, MARKET,
                                          ticker.id, API_NAME)

            # Обновление информации
            ticker.market_cap_rank = coin.get('market_cap_rank')
            ticker.name = coin.get('name')
            ticker.symbol = coin.get('symbol')

        db.session.commit()

        # Следующая страница
        page += 1

    # События
    api_event.update(API_NAME, new_ids, 'new_tickers', False)
    api_event.update(API_NAME, not_found_ids, 'not_found_tickers')

    # Инфо
    api_info.set('Тикеры обновлены', datetime.now(), API_NAME)

    # Следующий запуск
    if retry_after:
        self.default_retry_delay = retry_after
        self.retry()
