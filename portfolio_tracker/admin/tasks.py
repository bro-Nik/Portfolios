import os
import time
import pickle
from datetime import datetime, timedelta
from io import BytesIO
import requests

from PIL import Image
from flask import current_app

from portfolio_tracker.app import db, celery, redis
from portfolio_tracker.general_functions import get_price_list, redis_decode
from portfolio_tracker.models import PriceHistory, Ticker, WatchlistAsset
from portfolio_tracker.admin import currencylayer, polygon, coingecko
from portfolio_tracker.admin.utils import add_prefix, get_ticker, get_tickers, remove_prefix, task_log


def ticker_in_base(ticker_id, tickers):
    for ticker in tickers:
        if ticker.id == ticker_id:
            return ticker


@celery.task(bind=True, name='stocks_load_images')
def stocks_load_images(self):
    self.update_state(state='LOADING')
    market = 'stocks'
    task_log('Start load stocks images', market)

    tickers = db.session.execute(
        db.select(Ticker).filter_by(market=market, image=None)).scalars()

    for ticker in tickers:
        ticker_id = remove_prefix(ticker.id, market)
        image_url = polygon.get_image_url(ticker_id)
        if image_url:
            ticker.image = load_image(image_url, market, ticker_id)
            db.session.commit()
    task_log('End load stocks images', market)


@celery.task(bind=True, name='crypto_load_tickers')
def crypto_load_tickers(self):
    self.update_state(state='LOADING')
    market = 'crypto'
    task_log('Загрузка тикеров - Старт', market)

    tickers = list(get_tickers('crypto'))
    page = 1

    while True:
        data = coingecko.get_tickers(page)
        if not data:
            break

        for coin in data:
            ticker_id = add_prefix(coin['id'], market)

            ticker = ticker_in_base(ticker_id, tickers)
            if not ticker:
                ticker = Ticker(id=ticker_id, market=market)
                db.session.add(ticker)
                tickers.append(ticker)

            if not ticker.image:
                ticker.image = load_image(coin.get('image'), market, ticker_id)

            ticker.market_cap_rank = coin.get('market_cap_rank')
            ticker.name = coin.get('name')
            ticker.symbol = coin.get('symbol')

        db.session.commit()
        page += 1

    task_log('Загрузка тикеров - Конец', market)


@celery.task(bind=True, name='stocks_load_tickers')
def stocks_load_tickers(self):
    ''' загрузка тикеров с https://polygon.io/ '''
    self.update_state(state='LOADING')
    market = 'stocks'
    task_log('Start load stocks tickers', market)

    tickers = list(get_tickers(market))
    url = None

    while True:
        data = polygon.get_tickers(url)
        if not data:
            break

        for stock in data:
            ticker_id = add_prefix(stock['ticker'], market)
            ticker = ticker_in_base(ticker_id, tickers)

            if not ticker:
                ticker = Ticker(id=ticker_id, market=market)
                db.session.add(ticker)
                tickers.append(ticker)

            ticker.name = stock['name']
            ticker.symbol = stock['ticker']
        db.session.commit()

        url = data.get('next_url')
        if not url:
            break
        task_log('Load stocks tickers - next url', market)

    redis.delete(*['update_stocks'])
    task_log('End load stocks tickers', market)


@celery.task(bind=True, name='currency_load_tickers')
def currency_load_tickers(self):
    self.update_state(state='LOADING')
    market = 'currency'
    task_log('Start load currency tickers', market)

    data = currencylayer.get_currencies()
    if data:
        tickers = list(get_tickers(market))

        for currency in data:
            ticker_id = add_prefix(market, currency)
            ticker = ticker_in_base(ticker_id, tickers)
            if not ticker:
                ticker = Ticker(id=ticker_id, market=market, stable=True)
                db.session.add(ticker)
                tickers.append(ticker)

            ticker.name = data[currency]
            ticker.symbol = currency

        db.session.commit()

        redis.delete(*['update_currency'])

    task_log('End load currency tickers', market)


@celery.task(bind=True, name='crypto_load_prices', default_retry_delay=0,
             max_retries=None, ignore_result=True)
def crypto_load_prices(self):
    ''' Запрос цен у КоинГеко криптовалюта '''
    self.update_state(state='WORK')
    market = 'crypto'
    task_log('Загрузка цен - Старт', market)

    price_list = get_price_list('crypto')
    ids = [remove_prefix(ticker.id, market) for ticker in get_tickers(market)]

    # Делаем запросы кусками
    while ids:
        ids_str = ''
        while len(ids_str) < 1900 and ids:
            ids_str += ',' + ids[0]
            ids.pop(0)

        new_price_list = coingecko.get_prices(ids_str)
        if new_price_list:
            price_list = price_list | new_price_list
            redis.set('price_list_crypto', pickle.dumps(price_list))

    task_log('Загрузка цен - Конец', market)
    crypto_load_prices.retry()


@celery.task(bind=True, name='stocks_load_prices', default_retry_delay=300,
             max_retries=None, ignore_result=True)
def stocks_load_prices(self):
    ''' Запрос цен у Polygon фондовый рынок '''
    self.update_state(state='WORK')

    update_stocks = redis_decode('update-stocks', '')
    if update_stocks != str(datetime.now().date()):
        market = 'stocks'
        task_log('Start load stocks prices', market)

        new_price_list = polygon.get_prices()
        if new_price_list:
            price_list = get_price_list(market) | new_price_list
            redis.set('price_list_stocks', pickle.dumps(price_list))
            redis.set('update-stocks', str(datetime.now().date()))

        task_log('End load stocks prices', market)
    stocks_load_prices.retry()


@celery.task(bind=True, name='currency_load_prices', default_retry_delay=300,
             max_retries=None, ignore_result=True)
def currency_load_prices(self):
    ''' Запрос цен валюты '''
    self.update_state(state='WORK')

    update_currency = redis_decode('update-currency', '')
    if update_currency != str(datetime.now().date()):
        market = 'currency'
        task_log('Start load currency prices', market)

        new_price_list = currencylayer.get_prices()
        if new_price_list:
            price_list = get_price_list(market) | new_price_list
            redis.set('price_list_currency', pickle.dumps(price_list))
            redis.set('update-currency', str(datetime.now().date()))

        task_log('End load currency prices', market)
    currency_load_prices.retry()


@celery.task(bind=True, name='alerts_update', default_retry_delay=300,
             max_retries=None, ignore_result=True)
def alerts_update(self):
    ''' Функция собирает уведомления и проверяет нет ли сработавших '''
    self.update_state(state='WORK')

    price_list = get_price_list()
    tracked_tickers = db.session.execute(db.select(WatchlistAsset)).scalars()

    for ticker in tracked_tickers:
        if not ticker.alerts:
            continue

        price = price_list.get(ticker.ticker_id)
        if not price:
            continue

        for alert in ticker.alerts:
            if alert.status != 'on':
                continue

            if ((alert.type == 'down' and price <= alert.price)
                    or (alert.type == 'up' and price >= alert.price)):
                alert.status = 'worked'

    db.session.commit()
    alerts_update.retry()


# @celery.task(bind=True, name='currency_history', ignore_result=True)
# def load_currency_history(self):
def load_currency_history():

    date = datetime.now().date()
    market = 'currency'
    tickers = tuple(get_tickers(market))

    # ToDO потом убрать
    n = 0
    while n <= 3:
        date = date - timedelta(days=1)
        history = db.session.execute(db.select(PriceHistory)
                                     .filter_by(date=date)).scalar()
        if history:
            continue

        data = currencylayer.get_historical(date)
        n += 1

        if not data:
            return None

        for currency in data:
            ticker_id = add_prefix(currency[len('USD'):], market)
            ticker = ticker_in_base(ticker_id, tickers)

            if ticker:
                price = ticker.get_price(date)
                if not price:
                    ticker.set_price(date, 1 / data[currency])

        db.session.commit()
        print(str(date), ' loaded. Next currency history')
    print('End currency history')


def load_image(url, market, ticker_id):
    upload_folder = current_app.config['UPLOAD_FOLDER']
    path = f'{upload_folder}/images/tickers/{market}'
    os.makedirs(path, exist_ok=True)

    ticker_id = remove_prefix(ticker_id, market)

    try:
        r = requests.get(url)
        original_img = Image.open(BytesIO(r.content))
        filename = f'{ticker_id}.{original_img.format}'.lower()
    except Exception:
        return None

    def resize_image(px):
        size = (px, px)
        path_local = os.path.join(path, str(px))
        os.makedirs(path_local, exist_ok=True)
        path_saved = os.path.join(path_local, filename)
        original_img.resize(size).save(path_saved)

    resize_image(24)
    resize_image(40)

    return filename
