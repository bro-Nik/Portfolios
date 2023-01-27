from flask import session, Flask
from pycoingecko import CoinGeckoAPI
import os, json, requests, time
from datetime import datetime, timedelta
from celery.schedules import crontab
import pickle

from portfolio_tracker.app import app, db, celery, redis
from portfolio_tracker.models import Transaction, Asset, Wallet, Portfolio, Ticker, Market, Alert


cg = CoinGeckoAPI()
date = datetime.now().date()

settings_list = {}

@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(120.0, price_list_crypto_def.s())

def price_list_def():
    ''' Общая функция сбора цен '''
    for market in settings_list['markets']:
        if market == 'crypto':
            if not redis.get('price_list_crypto'):
                price_list_crypto_def()

        #if market == 'stocks':
        #    if price_list_stocks == {}:
        #        price_list_stocks_def()

    price_list_crypto = pickle.loads(redis.get('price_list_crypto')) if redis.get('price_list_crypto') else {}
    price_list_stocks = pickle.loads(redis.get('price_list_stocks')) if redis.get('price_list_stocks') else {}
    price_list = {**price_list_crypto, **price_list_stocks}

    return price_list


@celery.task
def price_list_crypto_def():
    ''' Запрос цен у КоинГеко криптовалюта '''
    price_list_crypto = pickle.loads(redis.get('price_list_crypto')) if redis.get('price_list_crypto') else {}
    if price_list_crypto == {}:
        market = db.session.execute(db.select(Market).filter_by(name='Crypto')).scalar()
        ids = []
        for ticker in market.tickers:
            if ticker.id:
                ids.append(ticker.id)
    else:
        # берем id тикеров из прайса
        ids = list(price_list_crypto.keys())
        ids.remove('update-crypto') # удаляем ключ времени обновления

    price_list = cg.get_price(vs_currencies='usd', ids=ids)
    if price_list:
        for ticker in ids:
            price_list[ticker] = price_list[ticker]['usd']

        price_list['update-crypto'] = str(datetime.now())
        redis.set('price_list_crypto', pickle.dumps(price_list))

        print('Крипто прайс обновлен ' + str(price_list['update-crypto']))
        alerts_update_def.delay()

@celery.task
def price_list_stocks_def():
    ''' Запрос цен у Polygon фондовый рынок '''
    with app.app_context():
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
                k = day % 4
                # задержка на бесплатном тарифе
                if k == 0:
                    print('Задержка 1 мин. (загрузка прайса Акции)')
                    time.sleep(60)

        if price_list:
            price_list['update-stocks'] = datetime.now()
            price_list_stocks = price_list
            print('Фондовый прайс обновлен ', price_list['update-stocks'])
            alerts_update_def()

@celery.task
def alerts_update_def():
    ''' Функция собирает уведомления и проверяет нет ли сработавших '''
    price_list_crypto = pickle.loads(redis.get('price_list_crypto')) if redis.get('price_list_crypto') else {}
    price_list_stocks = pickle.loads(redis.get('price_list_stocks')) if redis.get('price_list_stocks') else {}
    price_list = {**price_list_crypto, **price_list_stocks}
    flag = False
    all_alerts = pickle.loads(redis.get('all_alerts')) if redis.get('all_alerts') else {}
    # первый запрос уведомлений
    if all_alerts == {}:
        all_alerts['not_worked'] = {}
        all_alerts['worked'] = {}
        alerts_in_base = db.session.execute(db.select(Alert)).scalars()
        if alerts_in_base != ():
            for alert in alerts_in_base:
                if (alert.type == 'down' and float(price_list[alert.ticker_id]) <= alert.price) or (alert.type == 'up' and float(price_list[alert.ticker_id]) >= alert.price):
                    alert.worked = True
                    flag = True
                # если это сработавшее уведомление
                if alert.worked:
                    all_alerts['worked'][alert.id] = {}
                    all_alerts['worked'][alert.id]['price'] = alert.price
                    all_alerts['worked'][alert.id]['type'] = alert.type
                    all_alerts['worked'][alert.id]['comment'] = alert.comment
                    all_alerts['worked'][alert.id]['ticker'] = alert.ticker.name
                    all_alerts['worked'][alert.id]['ticker_id'] = alert.ticker_id
                    if alert.asset_id:
                        all_alerts['worked'][alert.id]['portfolio_id'] = alert.asset.portfolio_id
                        all_alerts['worked'][alert.id]['portfolio_name'] = alert.asset.portfolio.name
                    else:
                        all_alerts['worked'][alert.id]['market_id'] = alert.ticker.market_id
                # если это не сработавшее уведомление
                if not alert.worked:
                    all_alerts['not_worked'][alert.id] = {}
                    all_alerts['not_worked'][alert.id]['type'] = alert.type
                    all_alerts['not_worked'][alert.id]['price'] = alert.price
                    all_alerts['not_worked'][alert.id]['ticker_id'] = alert.ticker_id
        redis.set('all_alerts', pickle.dumps(all_alerts))

    # последующие запросы уведомлений без запроса в базу
    else:
        if all_alerts['not_worked'] != {}:
            for alert in list(all_alerts['not_worked'].keys()):
                if (all_alerts['not_worked'][alert]['type'] == 'down' and price_list[all_alerts['not_worked'][alert]['ticker_id']] <= all_alerts['not_worked'][alert]['price']) or (all_alerts['not_worked'][alert]['type'] == 'up' and price_list[all_alerts['not_worked'][alert]['ticker_id']] >= all_alerts['not_worked'][alert]['price']):
                    alert_in_base = db.session.execute(db.select(Alert).filter_by(id=alert)).scalar()
                    alert_in_base.worked = True
                    flag = True
                    # удаляем из несработавших
                    all_alerts['not_worked'].pop(alert)
                    # добавляем в сработавшие
                    all_alerts['worked'][alert_in_base.id] = {}
                    all_alerts['worked'][alert_in_base.id]['price'] = alert_in_base.price
                    all_alerts['worked'][alert_in_base.id]['type'] = alert_in_base.type
                    all_alerts['worked'][alert_in_base.id]['comment'] = alert_in_base.comment
                    all_alerts['worked'][alert_in_base.id]['ticker'] = alert_in_base.ticker.name
                    all_alerts['worked'][alert_in_base.id]['ticker_id'] = alert_in_base.ticker_id
                    if alert_in_base.asset_id:
                        all_alerts['worked'][alert_in_base.id]['portfolio_id'] = alert_in_base.asset.portfolio_id
                        all_alerts['worked'][alert_in_base.id]['portfolio_name'] = alert_in_base.asset.portfolio.name
                    else:
                        all_alerts['worked'][alert_in_base.id]['market_id'] = alert_in_base.ticker.market_id

    if flag:
        redis.set('all_alerts', pickle.dumps(all_alerts))
        db.session.commit()


def when_updated_def(when_updated):
    ''' Возвращает сколько прошло от входящей даты '''
    if type(when_updated) == str:
        when_updated = datetime.strptime(when_updated, '%Y-%m-%d %H:%M:%S.%f')

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


def smart_round(number):
    ''' Окрушление зависимое от величины числа для Jinja '''
    try:
        number = float(number)
        if number >= 100:
            number = round(number, 1)
        elif number >= 10:
            number = round(number, 2)
        elif number >= 1:
            number = round(number, 3)
        elif number >= 0.1:
            number = round(number, 5)
        elif number >= 0.0001:
            number = round(number, 7)

        return number
    except: # строка не является float / int
        return ''

app.add_template_filter(smart_round)

def number_group(number):
    ''' Разделитель тысяных для Jinja '''
    return "{:,}".format(number).replace(',', ' ')

app.add_template_filter(number_group)


