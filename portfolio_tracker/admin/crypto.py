import time
from collections.abc import Callable

from pycoingecko import CoinGeckoAPI

from portfolio_tracker.admin.utils import get_tickers, remove_prefix, \
    task_log, load_image, find_ticker_in_base
from portfolio_tracker.models import db


cg = CoinGeckoAPI()
MARKET = 'crypto'


def get_data(func: Callable, *args, **kwargs) -> dict | None:
    attempts: int = 5  # Допустимое количество попыток
    minute_calls: int | None = 30  # Допустимое количество вызовов в минуту

    while attempts > 0:
        attempts -= 1

        # Задержка, если ограничено количество вызовов в минуту
        if minute_calls:
            time.sleep(60 / minute_calls)

        try:
            data = func(*args, **kwargs)
            task_log('Удачный запрос', MARKET)
            return data
        except Exception as error:
            task_log(f'Неудача (осталось попыток:{attempts})-{error}', MARKET)
            # ToDo доработать ошибки
            raise


def load_prices() -> None:
    task_log('Загрузка цен - Старт', MARKET)

    tickers = get_tickers(MARKET)
    url = f'{cg.api_base_url}simple/price?vs_currencies=usd&ids='
    max_len = 2048 - len(url)
    tickers_to_do = []

    while tickers:

        # Разбиение запроса до допустимой длины
        ids = ''
        while (len(f'{ids},{remove_prefix(tickers[0].id, MARKET)}') < max_len
               and tickers):
            ids += ',' + remove_prefix(tickers[0].id, MARKET)
            tickers_to_do.append(tickers.pop(0))

        # Получение данных
        data = get_data(cg.get_price, vs_currencies='usd', ids=ids)
        if not data:
            return

        # Сохранение данных
        for ticker in tickers_to_do:
            ticker_in_data = data.get(remove_prefix(ticker.id, MARKET))
            if ticker_in_data:
                price = ticker_in_data.get('usd', 0)
                ticker.price = price
        db.session.commit()

    task_log('Загрузка цен - Конец', MARKET)


def load_tickers() -> None:
    task_log('Загрузка тикеров - Старт', MARKET)

    tickers = get_tickers(MARKET)
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
