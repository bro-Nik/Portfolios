import time
import requests

from flask import current_app

from portfolio_tracker.admin.utils import add_prefix


def key():
    return f"access_key={current_app.config['API_KEY_CURRENCYLAYER']}"


def get_data(url):
    errors_count = 0
    errors_max = 5

    while True:
        response = requests.get(url)
        data = response.json()

        if not data.get('error'):
            return data

        print(data['error'].get('info'))
        errors_count += 1
        if errors_count >= errors_max:
            return {}


def get_historical(date):
    url = f'http://api.currencylayer.com/historical?{key()}&date='
    data = get_data(url + str(date))
    return data.get('quotes')


def get_currencies():
    url = f'http://api.currencylayer.com/list?{key()}'
    data = get_data(url)
    return data.get('currencies')


def get_prices():
    url = f'http://api.currencylayer.com/live?{key()}'
    data = get_data(url)

    if data:
        market = 'currency'
        price_list = {}
        for ticker in data['quotes']:
            price_list[add_prefix(ticker, market)] = 1 / data['quotes'][ticker]
        if price_list:
            price_list[add_prefix('usd', market)] = 1
        return price_list
