import time
from datetime import datetime, timedelta
import requests

from flask import current_app

from portfolio_tracker.admin.utils import add_prefix


def key():
    return f"apiKey={current_app.config['API_KEY_POLYGON']}"


def get_data(url):
    response = requests.get(url)
    return response.json()


def get_image_url(ticker_id):
    time.sleep(15)

    url = f'https://api.polygon.io/v3/reference/tickers/{ticker_id}?{key()}'
    image_url = None

    try:
        data = get_data(url)
        image_url = f"{data['results']['branding']['icon_url']}?{key()}"
        if image_url:
            time.sleep(15)
            return image_url
    except Exception:
        return None


def get_tickers(url=None):
    time.sleep(15)

    if not url:
        url = ('https://api.polygon.io/v3/reference/tickers?market=stocks&'
               'active=true&order=asc&limit=1000')
    url += f'&apiKey={key()}'

    data = get_data(url)
    if data.get('results'):
        return data['results']


def get_prices():
    day = 0

    while True:
        # вчерашняя цена закрытия, т.к. бесплатно
        day += 1
        # задержка на бесплатном тарифе
        if day % 4 == 0:
            time.sleep(60)

        date = datetime.now().date() - timedelta(days=day)
        url = (f'https://api.polygon.io/v2/aggs/grouped/locale/us/market/'
               f'stocks/{date}?adjusted=true&include_otc=false&{key()}')

        data = get_data(url)
        if data:
            price_list = {}
            for ticker in data['results']:
                price_list[add_prefix(ticker, 'stocks')] = ticker['c']
            return price_list
