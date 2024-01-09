from datetime import datetime
import time
from pycoingecko import CoinGeckoAPI

from portfolio_tracker.admin.utils import add_prefix, task_log


cg = CoinGeckoAPI()
market = 'crypto'


def get_tickers(page):
    time.sleep(10)
    data = True
    errors = 0

    try:
        data = cg.get_coins_markets('usd', per_page='200', page=page)
        if data[0]['id']:
            task_log('Загрузка тикеров - Следующий запрос', market)
            return data
    except Exception:
        task_log('Загрузка тикеров - Ошибка. Сплю', market)
        errors += 1
        time.sleep(60)

    if errors > 5:
        task_log('Загрузка тикеров - Превышено количество ошибок', market)
        return None


def get_prices(ids):
    data = ''
    errors = 0

    while data == '':
        time.sleep(15)
        try:
            data = cg.get_price(vs_currencies='usd', ids=ids)
            task_log('Загрузка цен - Следующий запрос', market)
        except Exception:
            task_log('Загрузка цен - Ошибка. Сплю', market)
            errors += 1

    if errors > 5:
        task_log('Загрузка цен - Превышено количество ошибок', market)
        return None

    price_list = {}
    for id in data:
        price_list[add_prefix(id, market)] = data[id].get('usd', 0)

    return price_list
