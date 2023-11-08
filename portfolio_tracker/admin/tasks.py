import os
from pycoingecko import CoinGeckoAPI
import requests
from io import BytesIO
from PIL import Image
from flask import current_app
import time
from datetime import datetime, timedelta
import pickle
from portfolio_tracker.admin.utils import get_tickers

from portfolio_tracker.general_functions import get_price_list, redis_decode
from portfolio_tracker.models import PriceHistory, Ticker, WatchlistAsset
from portfolio_tracker.app import db, celery, redis

cg = CoinGeckoAPI()


@celery.task(bind=True, name='load_stocks_images')
def load_stocks_images(self):
    self.update_state(state='LOADING')
    print('Start load stocks images')

    prefix = current_app.config['STOCKS_PREFIX']
    key = current_app.config['API_KEY_POLYGON']

    # tickers = db.session.execute(
    #     db.select(Ticker).filter(Ticker.market == 'stocks',
    #                              Ticker.image.is_(None))).scalars()
    tickers = db.session.execute(
        db.select(Ticker).filter(Ticker.market == 'stocks')).scalars()

    def get_image_url(url):
        try:
            r = requests.get(url)
            result = r.json()
            url = f"{result['results']['branding']['icon_url']}?apiKey={key}"
            return url
        except Exception:
            return None

    for ticker in tickers:
        id = ticker.id.upper()[len(prefix):]
        url = f'https://api.polygon.io/v3/reference/tickers/{id}?apiKey={key}'
        time.sleep(15)

        image_url = get_image_url(url)
        if image_url:
            time.sleep(15)
            ticker.image = load_image(image_url, 'stocks', id)
            db.session.commit()
    print('End load stocks images')


@celery.task(bind=True, name='crypto_tickers')
def crypto_tickers(self):
    ''' загрузка тикеров с https://www.coingecko.com/ru/api/ '''
    self.update_state(state='LOADING')
    print('Load crypto tickers')

    tickers = tuple(get_tickers('crypto'))
    prefix = current_app.config['CRYPTO_PREFIX']

    def ticker_in_base(id):
        for ticker in tickers:
            if ticker.id == id:
                return ticker

    page = 1
    new_tickers = {}
    query = True
    while query != []:
        try:
            query = cg.get_coins_markets('usd', per_page='200', page=page)
            query[0]['id']
            print('Crypto page ' + str(page))
        except Exception:
            print('not query... sleep...')
            time.sleep(60)
            continue

        for coin in query:
            id = prefix + coin['id'].lower()
            if id in new_tickers:
                continue

            ticker = ticker_in_base(id)
            if not ticker:
                ticker = Ticker(
                    id=id,
                    market='crypto',
                    name=coin.get('name'),
                    symbol=coin.get('symbol'),
                    image=load_image(coin.get('image'), 'crypto', id)
                )
                db.session.add(ticker)
                new_tickers[id] = 0

            elif not ticker.image:
                ticker.image = load_image(coin.get('image'), 'crypto', id)

            ticker.market_cap_rank = coin.get('market_cap_rank')

        db.session.commit()

        page += 1
        time.sleep(10)

    print('crypto end')


@celery.task(bind=True, name='stocks_tickers')
def stocks_tickers(self):
    ''' загрузка тикеров с https://polygon.io/ '''
    self.update_state(state='LOADING')
    print('Load stocks tickers')

    key = current_app.config['API_KEY_POLYGON']
    tickers = get_tickers('stocks')
    tickers_in_base = [ticker.id for ticker in tickers]
    prefix = current_app.config['STOCKS_PREFIX']
    new_tickers = False

    date = datetime.now().date()
    url = (f'https://api.polygon.io/v3/reference/tickers?market=stocks&'
           f'date={date}&active=true&order=asc&limit=1000&apiKey={key}')

    while url:
        response = requests.get(url)
        data = response.json()
        if not data.get('results'):
            print('stocks Error :', data)
            time.sleep(15)
            continue

        for ticker in data['results']:
            id = prefix + ticker['ticker'].lower()
            if id not in tickers_in_base:
                new_ticker = Ticker(
                    id=id,
                    name=ticker['name'],
                    symbol=ticker['ticker'],
                    market='stocks'
                )
                db.session.add(new_ticker)
                tickers_in_base.append(id)
                new_tickers = True
        db.session.commit()

        next_url = data.get('next_url')
        url = f'{next_url}&apiKey={key}' if next_url else None
        print('Stocks next url')
        time.sleep(15)

    if new_tickers:
        redis.delete(*['update_stocks'])
    print('stocks tickers end')


@celery.task(bind=True, name='currency_tickers')
def currency_tickers(self):
    ''' загрузка тикеров с https://currencylayer.com '''
    self.update_state(state='LOADING')
    print('Load currency tickers')

    key = current_app.config['API_KEY_CURRENCYLAYER']
    prefix = current_app.config['CURRENCY_PREFIX']
    tickers_in_base = [ticker.id for ticker in get_tickers('currency')]
    new_tickers = False

    url = f'http://api.currencylayer.com/list?access_key={key}'

    response = requests.get(url)
    data = response.json()
    while data['success'] is not True:
        print('currency Error :', data)
        time.sleep(15)

    tickers = data['currencies']
    for ticker in tickers:
        id = prefix + ticker.lower()
        if id not in tickers_in_base:
            new_ticker = Ticker(
                id=id,
                name=tickers[ticker],
                symbol=ticker,
                market='currency',
                stable=True
            )
            db.session.add(new_ticker)
            tickers_in_base.append(id)
            new_tickers = True
    db.session.commit()

    if new_tickers:
        redis.delete(*['update_currency'])
    print('currency tickers end')


@celery.task(bind=True, name='prices_crypto', default_retry_delay=0,
             max_retries=None, ignore_result=True)
def prices_crypto(self):
    ''' Запрос цен у КоинГеко криптовалюта '''
    self.update_state(state='WORK')

    prefix = current_app.config['CRYPTO_PREFIX']
    price_list = get_price_list('crypto')
    ids = [ticker.id[len(prefix):] for ticker in get_tickers('crypto')]

    # Делаем запросы кусками
    while ids:
        ids_str = ''
        while len(ids_str) < 1900 and ids:
            ids_str += ',' + ids[0]
            ids.pop(0)

        data = ''
        while data == '':
            try:
                data = cg.get_price(vs_currencies='usd', ids=ids_str)
                print("New page")
            except Exception:
                print("Соединение отклонено сервером... Сплю. ZZzzzz")
                time.sleep(15)

        for id in data:
            price_list[prefix + id] = data[id].get('usd', 0)

        if price_list:
            redis.set('price_list_crypto', pickle.dumps(price_list))
        time.sleep(17)

    print("End load crypto price")
    prices_crypto.retry()


@celery.task(bind=True, name='prices_stocks', default_retry_delay=300,
             max_retries=None, ignore_result=True)
def prices_stocks(self):
    ''' Запрос цен у Polygon фондовый рынок '''
    self.update_state(state='WORK')

    update_stocks = redis_decode('update-stocks', '')

    if update_stocks == str(datetime.now().date()):
        prices_stocks.retry()
        return ''

    price_list = get_price_list('stocks')
    key = current_app.config['API_KEY_POLYGON']
    prefix = current_app.config['STOCKS_PREFIX']

    day = 0
    data = {}
    while not data.get('results'):
        day += 1
        # задержка на бесплатном тарифе
        if day % 4 == 0:
            time.sleep(60)

        date = datetime.now().date() - timedelta(days=day)
        url = (f'https://api.polygon.io/v2/aggs/grouped/locale/us/market/'
               f'stocks/{date}?adjusted=true&include_otc=false&apiKey={key}')

        response = requests.get(url)
        data = response.json()

    for ticker in data['results']:
        # вчерашняя цена закрытия, т.к. бесплатно
        id = ticker['T'].lower()
        price_list[prefix + id] = ticker['c']

    if price_list:
        redis.set('update-stocks', str(datetime.now().date()))
        redis.set('price_list_stocks', pickle.dumps(price_list))

    print("End load stocks price")
    prices_stocks.retry()


@celery.task(bind=True, name='prices_currency', default_retry_delay=300,
             max_retries=None, ignore_result=True)
def prices_currency(self):
    ''' Запрос цен валюты '''
    self.update_state(state='WORK')

    update_currency = redis_decode('update-currency', '')

    if update_currency == str(datetime.now().date()):
        prices_currency.retry()
        return ''

    price_list = get_price_list('currency')
    key = current_app.config['API_KEY_CURRENCYLAYER']
    prefix = current_app.config['CURRENCY_PREFIX']

    url = f'http://api.currencylayer.com/live?access_key={key}'
    response = requests.get(url)
    data = response.json()
    while data.get('success') is not True:
        print('currency Error :', data)
        time.sleep(15)

    price_list[prefix + 'usd'] = 1

    for ticker in data['quotes']:
        id = ticker[3:].lower()
        price_list[prefix + id] = 1 / data['quotes'][ticker]

    if price_list:
        redis.set('update-currency', str(datetime.now().date()))
        redis.set('price_list_currency', pickle.dumps(price_list))

    print('End load currency price')
    prices_currency.retry()


@celery.task(bind=True, name='alerts_update', default_retry_delay=180,
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


@celery.task()
def load_currency_history():
    key = current_app.config['API_KEY_CURRENCYLAYER']
    prefix = current_app.config['CURRENCY_PREFIX']

    tickers = tuple(get_tickers('currency'))

    url = f'http://api.currencylayer.com/historical?access_key={key}&date='

    def get_ticker(id):
        for ticker in tickers:
            if ticker.id == id:
                return ticker

    def get_data(date):
        response = requests.get(url + str(date))
        return response.json()

    day = 1
    history = True
    date = datetime.now().date() - timedelta(days=day)
    while history:
        day += 1
        date = datetime.now().date() - timedelta(days=day)
        history = db.session.execute(db.select(PriceHistory)
                                     .filter_by(date=date)).scalar()
        print(date, ' history', bool(history))

    n = 0
    while n <= 300:
        date = date - timedelta(days=1)
        data = get_data(date)
        while data.get('success') is not True:
            print('currency Error :', data)
            time.sleep(15)
            data = get_data(date)

        if not data['quotes']:
            continue

        for ticker in data['quotes']:
            id = prefix + ticker[3:].lower()
            ticker_in_base = get_ticker(id)

            if ticker_in_base:
                ticker_history = db.session.execute(
                    db.select(PriceHistory)
                    .filter_by(date=date,
                               ticker_id=ticker_in_base.id)).scalar()
                if ticker_history:
                    continue

                db.session.add(
                    PriceHistory(date=date, ticker_id=ticker_in_base.id,
                                 price_usd=1 / data['quotes'][ticker]))

        db.session.commit()
        print(str(date), ' loaded. Next currency history')
        time.sleep(15)
        n += 1
    print('End currency history')


def load_image(url, market, ticker_id):
    upload_folder = current_app.config['UPLOAD_FOLDER']
    path = f'{upload_folder}/images/tickers/{market}'
    os.makedirs(path, exist_ok=True)

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
