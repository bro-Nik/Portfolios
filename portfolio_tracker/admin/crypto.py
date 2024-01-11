import time
from pycoingecko import CoinGeckoAPI

from portfolio_tracker.admin.utils import get_tickers, remove_prefix, \
    task_log, load_image, find_ticker_in_base
from portfolio_tracker.models import db


cg = CoinGeckoAPI()
MARKET = 'crypto'


def get_data(func, *args, **kwargs):
    max_attempts = 5  # Допустимое количество попыток
    minute_calls = 30  # Допустимое количество вызовов в минуту

    while max_attempts > 0:
        max_attempts -= 1

        # Задержка, если ограничено количество вызовов в минуту
        if minute_calls:
            time.sleep(60 / minute_calls)

        try:
            data = func(*args, **kwargs)
            task_log('Удачный запрос', MARKET)
            return data
        except Exception as error:
            task_log(f'Неудачный запрос (осталось {max_attempts} попыток) - {error}', MARKET)


def load_prices():
    task_log('Загрузка цен - Старт', MARKET)

    tickers = list(get_tickers(MARKET))
    max_len = 2048 - len(f'{cg.api_base_url}simple/price?ids=&vs_currencies=usd')
    tickers_to_do = []

    while tickers:

        # Разбиение запроса до допустимой длины
        ids = ''
        while len(f'{ids},{remove_prefix(tickers[0].id, MARKET)}') < max_len and tickers:
            ids += ',' + remove_prefix(tickers[0].id, MARKET)
            tickers_to_do.append(tickers.pop(0))

        # Получение данных
        data = get_data(cg.get_price, vs_currencies='usd', ids=ids)
        if not data:
            return None

        # Сохранение данных
        for ticker in tickers_to_do:
            ticker_in_data = data.get(remove_prefix(ticker.id, MARKET))
            if ticker_in_data:
                price = ticker_in_data.get('usd', 0)
                ticker.price = price
        db.session.commit()

    task_log('Загрузка цен - Конец', MARKET)


def load_tickers():
    task_log('Загрузка тикеров - Старт', MARKET)

    tickers = list(get_tickers('crypto'))
    page = 1

    while True:

        # Получение данных
        data = get_data(cg.get_coins_markets, 'usd', per_page='200', page=page)
        if not data:
            break

        # Сохранение данных
        for coin in data:

            # Поиск или добавление нового тикера
            external_id = coin['id']
            ticker = find_ticker_in_base(external_id, tickers, MARKET, True)
            if not ticker:
                continue

            # Добавление иконки
            if not ticker.image:
                ticker.image = load_image(coin.get('image'), MARKET, ticker.id)

            # Обновление информации
            ticker.market_cap_rank = coin.get('market_cap_rank')
            ticker.name = coin.get('name')
            ticker.symbol = coin.get('symbol')

        db.session.commit()

        # Следующая страница
        page += 1

    task_log('Загрузка тикеров - Конец', MARKET)
