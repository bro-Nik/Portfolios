from flask import session, g
from pycoingecko import CoinGeckoAPI
import os, json, requests, time
from tqdm import tqdm
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta
from threading import Timer
from threading import Thread

from portfolio_tracker import app, db
from portfolio_tracker.models import Transaction, Asset, Wallet, Portfolio, Ticker, Market, Alert
from portfolio_tracker import *


cg = CoinGeckoAPI()
date = datetime.now().date()

settings_list = {}
price_list_crypto = {}
price_list_stocks = {}
triggered_alerts = {}


def price_list_def():
    ''' Общая функция сбора цен '''
    global settings_list, price_list_crypto, price_list_stocks
    for market in settings_list['markets']:
        if market == 'crypto':
            price_list_crypto = price_list_crypto_def() if price_list_crypto == {} else price_list_crypto
        if market == 'stocks':
            price_list_stocks = price_list_stocks_def() if price_list_stocks == {} else price_list_stocks
    price_list = {**price_list_crypto, **price_list_stocks}

    return price_list


def price_list_crypto_def():
    ''' Запрос цен у КоинГеко криптовалюта '''
    with app.test_request_context():
        global price_list_crypto
        market = db.session.execute(db.select(Market).filter_by(name='Crypto')).scalar()
        ids = []
        for ticker in market.tickers:
            if ticker.id:
                ids.append(ticker.id)
        price_list = cg.get_price(vs_currencies='usd', ids=ids)
        if price_list:
            for ticker in market.tickers:
                if ticker.id:
                    price_list[ticker.id] = price_list[ticker.id]['usd']

            price_list['update-crypto'] = datetime.now()
            price_list_crypto = price_list
            print('Крипто прайс обновлен ', price_list['update-crypto'], ' Период ', settings_list['update_period']['crypto'], 'мин')
            alerts_update_def()
        else:
            price_list = price_list_crypto

        if settings_list['update_period']['crypto'] > 0:
            Timer(settings_list['update_period']['crypto']*60, price_list_crypto_def).start()
        else:
            Timer(86400, price_list_crypto_def).start()

        return price_list


def price_list_stocks_def():
    ''' Запрос цен у Polygon фондовый рынок '''
    with app.test_request_context():
        global price_list_stocks
        price_list = {}
        day = 1
        while price_list == {}:
            date = datetime.now().date() - timedelta(days=day)
            url = 'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/' + str(date) + '?adjusted=true&include_otc=false&apiKey=' + settings_list['api_key_polygon']
            response = requests.get(url)
            data = response.json()
            if data.get('results'):
                for ticker in data['results']:
                    # вчерашняя цена закрытия, т.к. бесплатно
                    price_list[ticker['T'].lower()] = ticker['c']
            else:
                # если нет результата, делаем запрос еще на 1 день раньше (возможно праздники)
                day += 1
                # задержка на бесплатном тарифе
                print('Задержка 15 сек (загрузка прайса Акции)')
                time.sleep(15)

        if price_list:
            price_list['update-stocks'] = datetime.now()
            price_list_stocks = price_list
            print('Фондовый прайс обновлен ', price_list['update-stocks'], ' Период ', settings_list['update_period']['stocks'], 'мин')
            alerts_update_def()
        else:
            price_list = price_list_stocks

        if settings_list['update_period']['stocks'] > 0:
            Timer(settings_list['update_period']['stocks'] * 60, price_list_stocks_def).start()
        else:
            Timer(86400, price_list_stocks_def).start()

        return price_list


def alerts_update_def():
    ''' Функция проверяет нет ли сработавших уведомлений '''
    alerts_in_base = db.session.execute(db.select(Alert).filter_by(worked=None)).scalars()
    price_list = {**price_list_crypto, **price_list_stocks}
    flag = False
    if alerts_in_base != ():
        for alert in alerts_in_base:
            if (alert.type == 'down' and price_list[alert.ticker_id] <= alert.price) or (alert.type == 'up' and price_list[alert.ticker_id] >= alert.price):
                alert.worked = True
                flag = True

    if flag:
        db.session.commit()
    if flag or triggered_alerts == {}:
        alerts_query_def()

def alerts_query_def():
    ''' Запрос сработавших уведомлений '''
    global triggered_alerts
    alerts_worked = db.session.execute(db.select(Alert).filter_by(worked=True)).scalars()

    for alert in alerts_worked:
        triggered_alerts[alert.id] = {}
        triggered_alerts[alert.id]['price'] = alert.price
        triggered_alerts[alert.id]['type'] = alert.type
        triggered_alerts[alert.id]['comment'] = alert.comment
        triggered_alerts[alert.id]['ticker'] = alert.ticker.name
        triggered_alerts[alert.id]['ticker_id'] = alert.ticker_id
        if alert.asset_id:
            triggered_alerts[alert.id]['portfolio_id'] = alert.asset.portfolio_id
            triggered_alerts[alert.id]['portfolio_name'] = alert.asset.portfolio.name
        else:
            triggered_alerts[alert.id]['market_id'] = alert.ticker.market_id
    print('алерты обновили')


def when_updated_def(when_updated):
    ''' Возвращает сколько прошло от входящей даты '''
    delta_time = datetime.now() - when_updated
    if date == datetime.date(when_updated):
        if delta_time.total_seconds() < 60:
            result = 'менее минуты'
        if 60 <= delta_time.total_seconds() < 3600:
            result = str(int(delta_time.total_seconds() / 60)) + ' мин.'
        if 3600 <= delta_time.total_seconds() < 86400:
            result = str(int(delta_time.total_seconds() / 3600)) + ' ч.'
    elif 0 < (date - datetime.date(when_updated)).days < 2:
        result = 'вчера'
    elif 2 <= (date - datetime.date(when_updated)).days < 10:
        result = str((date - datetime.date(when_updated)).days) + 'д. назад'
    else:
        result = str(datetime.date(when_updated))
    return result


def load_crypto_tickers(stop_load, market_id):
    ''' загрузка тикеров с https://www.coingecko.com/ru/api/ '''
    market_cap_rank = 0
    page = 1
    tickers_in_base = db.session.execute(db.select(Ticker).filter_by(market_id=market_id)).scalars()
    tickers_list = []
    if tickers_in_base != ():
        for ticker in tickers_in_base:
            tickers_list.append(ticker.id)
    while int(stop_load) > int(market_cap_rank):
        coins_list_markets = cg.get_coins_markets('usd', per_page='200', page=page)
        page += 1

        for coin in coins_list_markets:
            if coin['id'].lower() not in tickers_list:
                new_ticker = Ticker(
                    id=coin['id'].lower(),
                    name=coin['name'],
                    symbol=coin['symbol'],
                    market_cap_rank=coin['market_cap_rank'],
                    market_id=market_id,
                    image=coin['image']
                )
                db.session.add(new_ticker)
            market_cap_rank += 1
            if market_cap_rank >= int(stop_load):
                break
        db.session.commit()

def load_stocks_tickers(stop_load, market_id):
    ''' загрузка тикеров с https://polygon.io/ '''
    market_cap_rank = 0
    page = 1
    tickers_in_base = db.session.execute(db.select(Ticker).filter_by(market_id=market_id)).scalars()
    tickers_list = []
    if tickers_in_base != ():
        for ticker in tickers_in_base:
            tickers_list.append(ticker.id)
    url = 'https://api.polygon.io/v3/reference/tickers?market=stocks&date=2022-12-30&active=true&order=asc&apiKey=' + settings_list['api_key_polygon']
    response = requests.get(url)
    data = response.json()
    for ticker in data['results']:
        # ставим префикс, чтобы id не повторялись
        if ticker['ticker'].lower() not in tickers_list:
            new_ticker = Ticker(
                id=ticker['ticker'].lower(),
                name=ticker['name'],
                symbol=ticker['ticker'],
                market_id=market_id
            )
        db.session.add(new_ticker)
    db.session.commit()


def tickers_load(market_id):
    ''' Загрузка тикеров '''
    market_in_base = db.session.execute(db.select(Market).filter_by(id=market_id)).scalar()
    if market_in_base:
        if market_id == 'crypto':
            load_crypto_tickers(99, market_in_base.id)
        if market_id == 'stocks':
            load_stocks_tickers(99, market_in_base.id)
