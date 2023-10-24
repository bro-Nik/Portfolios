import json
import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw
from flask import Response, render_template, redirect, send_file, url_for, request, Blueprint
from flask_login import current_user
from sqlalchemy import func
import time
from datetime import datetime, timedelta
import pickle
from pycoingecko import CoinGeckoAPI
from celery.result import AsyncResult

from portfolio_tracker.general_functions import get_price_list, redis_decode_or_other, when_updated
from portfolio_tracker.models import Asset, Portfolio, PriceHistory, Ticker, Transaction, User, Wallet, WalletAsset, WatchlistAsset
from portfolio_tracker.user.user import user_delete_def
from portfolio_tracker.wraps import admin_only
from portfolio_tracker.app import app, db, celery, redis


admin = Blueprint('admin', __name__, template_folder='templates', static_folder='static')
cg = CoinGeckoAPI()


def get_tickers(market=None):
    select = db.select(Ticker)
    if market:
        select = select.filter_by(market=market)
    return db.session.execute(select).scalars()


@admin.route('/first_start', methods=['GET'])
@admin_only
def first_start():
    demo_user = db.session.execute(db.select(User).
                                   filter_by(type='demo')).scalar()
    if not demo_user:
        # demo user
        demo_user = User(email='demo@demo', password='demo', type='demo')
        db.session.add(demo_user)
        demo_user.wallets.append(Wallet(name='Default'))
        current_user.type = 'admin'
        db.session.commit()

    currencies = db.session.execute(db.select(Ticker).
                                   filter_by(market='currency')).scalar()
    if not currencies:
        # fiat money
        prefix = app.config['CURRENCY_PREFIX']
        db.session.add_all(
            [Ticker(id=prefix + 'usd', name='US Dollar', symbol='usd', market='currency', stable=True), 
             Ticker(id=prefix + 'rub', name='Russian Ruble', symbol='rub', market='currency', stable=True),
             Ticker(id=prefix + 'eur', name='Euro', symbol='eur', market='currency', stable=True),
             Ticker(id=prefix + 'jpy', name='Japanese Yen', symbol='jpy', market='currency', stable=True)])
        db.session.commit()


    return redirect(url_for('.index'))


@admin.route('/', methods=['GET'])
@admin_only
def index():
    return render_template('admin/index.html')


@admin.route('/index_detail', methods=['GET'])
@admin_only
def index_detail():
    def state(task):
        if task.id:
            if task.state in ['WORK']:
                return 'Работает'
            elif task.state in ['RETRY']:
                return 'Ожидает'
            elif task.state == 'LOADING':
                return 'Загрузка'
            elif task.state == 'REVOKED':
                return 'Остановлено'
            elif task.state == 'SUCCESS':
                return 'Готово'
            elif task.state == 'FAILURE':
                return 'Ошибка'
            else:
                return task.state
        else:
            return ''

    def get_tickers_count(market):
        return db.session.execute(db.select(func.count()).select_from(Ticker)
                                  .filter_by(market=market)).scalar()

    def get_users_count(type=None):
        select = db.select(func.count()).select_from(User)
        if type:
            select = select.filter_by(type=type)
        return db.session.execute(select).scalar()

    task_crypto_tickers = AsyncResult(redis_decode_or_other('crypto_tickers_task_id', ''))
    task_crypto_price = AsyncResult(redis_decode_or_other('crypto_price_task_id', ''))
    task_stocks_tickers = AsyncResult(redis_decode_or_other('stocks_tickers_task_id', ''))
    task_stocks_price = AsyncResult(redis_decode_or_other('stocks_price_task_id', ''))
    task_stocks_image = AsyncResult(redis_decode_or_other('stocks_image_task_id', ''))
    task_alerts = AsyncResult(redis_decode_or_other('alerts_task_id', ''))

    task_currency_tickers = AsyncResult(redis_decode_or_other('currency_tickers_task_id', ''))
    task_currency_price = AsyncResult(redis_decode_or_other('currency_price_task_id', ''))

    return {
        "users_count": get_users_count(),
        "admins_count": get_users_count('admin'),
        "task_alerts_id": task_alerts.id,
        "task_alerts_state": state(task_alerts),
        "crypto": {
            "tickers_count": get_tickers_count('crypto'),
            "task_tickers_id": task_crypto_tickers.id,
            "task_tickers_state": state(task_crypto_tickers),
            "task_price_id": task_crypto_price.id,
            "task_price_state": state(task_crypto_price),
            "price_when_update": when_updated(redis_decode_or_other('update-crypto'), '-')
        },
        "stocks": {
            "tickers_count": get_tickers_count('stocks'),
            "task_tickers_id": task_stocks_tickers.id,
            "task_tickers_state": state(task_stocks_tickers),
            "task_price_id": task_stocks_price.id,
            "task_price_state": state(task_stocks_price),
            "task_image_id": task_stocks_image.id,
            "task_image_state": state(task_stocks_image),
            "price_when_update": when_updated(redis_decode_or_other('update-stocks'), '-')
        },
        "currency": {
            "tickers_count": get_tickers_count('currency'),
            "task_tickers_id": task_currency_tickers.id,
            "task_tickers_state": state(task_currency_tickers),
            "task_price_id": task_currency_price.id,
            "task_price_state": state(task_currency_price),
            # "task_image_id": task_stocks_image.id,
            # "task_image_state": state(task_stocks_image),
            "price_when_update": when_updated(redis_decode_or_other('update-currency'), '-')
        },
    }


@admin.route('/index_action', methods=['GET'])
@admin_only
def index_action():

    def task_stop(key):
        task_id = redis.get(key)
        if task_id:
            celery.control.revoke(task_id.decode(), terminate=True)
            redis.delete(key)
            redis.delete('celery-task-meta-' + str(task_id.decode()))
            
    action = request.args.get('action')
    if action == 'crypto_tickers_start':
        task_stop('crypto_tickers_task_id')
        redis.set('crypto_tickers_task_id', str(load_crypto_tickers.delay().id))
    elif action == 'stocks_tickers_start':
        task_stop('stocks_tickers_task_id')
        redis.set('stocks_tickers_task_id', str(load_stocks_tickers.delay().id))
    elif action == 'currency_tickers_start':
        task_stop('currency_tickers_task_id')
        redis.set('currency_tickers_task_id', str(load_currency_tickers.delay().id))
    if action == 'crypto_price_start':
        task_stop('crypto_price_task_id')
        redis.set('crypto_price_task_id', str(price_list_crypto_def.delay().id))
    elif action == 'stocks_price_start':
        task_stop('stocks_price_task_id')
        redis.set('stocks_price_task_id', str(price_list_stocks_def.delay().id))
    elif action == 'currency_price_start':
        task_stop('currency_price_task_id')
        redis.set('currency_price_task_id', str(price_list_currency_def.delay().id))
    elif action == 'stocks_image_start':
        task_stop('stocks_images_task_id')
        redis.set('stocks_images_task_id', str(load_stocks_images.delay().id))
    elif action == 'alerts_start':
        task_stop('alerts_task_id')
        redis.set('alerts_task_id', str(alerts_update.delay().id))

    elif action == 'crypto_tickers_stop':
        task_stop('crypto_tickers_task_id')
    elif action == 'stocks_tickers_stop':
        task_stop('stocks_tickers_task_id')
    elif action == 'currency_tickers_stop':
        task_stop('currency_tickers_task_id')
    elif action == 'crypto_price_stop':
        task_stop('crypto_price_task_id')
    elif action == 'stocks_price_stop':
        task_stop('stocks_price_task_id')
    elif action == 'currency_price_stop':
        task_stop('currency_price_task_id')
    elif action == 'stocks_image_stop':
        task_stop('stocks_images_task_id')
    elif action == 'alerts_stop':
        task_stop('alerts_task_id')

    elif action == 'redis_delete_all':
        keys = redis.keys('*')
        redis.delete(*keys)
    elif action == 'redis_delete_all_tasks':
        keys = ['crypto_price_task_id', 'stocks_price_task_id',
                'alerts_task_id', 'crypto_tickers_task_id',
                'stocks_tickers_task_id', 'stocks_images_task_id']
        redis.delete(*keys)
        k = redis.keys('celery-task-meta-*')
        if k:
            redis.delete(*k)

    elif action == 'redis_delete_price_lists':
        keys = ['price_list_crypto', 'price_list_stocks', 'update-crypto',
                'update-stocks']
        redis.delete(*keys)
    elif action == 'clear':
        clear()

    return redirect(url_for('.index'))


@admin.route('/users', methods=['GET'])
@admin_only
def users():
    return render_template('admin/users.html')


@admin.route('/users_detail', methods=['GET'])
@admin_only
def users_detail():
    users = tuple(db.session.execute(db.select(User)).scalars())

    result = {"total": len(users),
              "totalNotFiltered": len(users),
              "rows": []}
    for user in users:
        u = {"id": '<input class="form-check-input to-check" type="checkbox" value="' + str(user.id) + '">',
             "email": user.email,
             "type": user.type,
             "portfolios": len(user.portfolios)}
        if user.info:
             u['first_visit'] = user.info.first_visit
             u['last_visit'] = user.info.last_visit
             u['country'] = user.info.country
             u['city'] = user.info.city
        result['rows'].append(u)

    return result


@admin.route('/users/action', methods=['POST'])
@admin_only
def users_action():
    data = json.loads(request.data) if request.data else {}

    action = data.get('action')
    ids = data['ids']

    for user_id in ids:
        if action == 'user_to_admin':
            user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar()
            user.type = 'admin'
            db.session.commit()
        elif action == 'admin_to_user':
            user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar()
            user.type = ''
            db.session.commit()

        elif action == 'delete':
            user_delete_def(user_id)

    return ''


@admin.route('/imports', methods=['GET'])
@admin_only
def imports():
    return render_template('admin/imports.html')


@admin.route('/export_tickers', methods=['GET'])
@admin_only
def export_tickers():
    tickers = db.session.execute(db.select(Ticker)).scalars()
    result = []
    prefixes = {'crypto': 'cr-', 'stocks': 'st-', 'currency': 'cu-'}

    for ticker in tickers:
        result.append({
            'id': ticker.id,
            'name': ticker.name,
            'symbol': ticker.symbol,
            'image': ticker.image,
            'market_cap_rank': ticker.market_cap_rank,
            'market': ticker.market,
            'stable': ticker.stable,
            'prefix': prefixes[ticker.market]
        })

    filename = 'tickers_export (' + str(datetime.now().date()) +').txt'

    return Response(json.dumps(result),
                    mimetype='application/json',
		            headers={'Content-disposition': 'attachment; filename=' + filename})


@admin.route('/tickers/action', methods=['POST'])
@admin_only
def tickers_action():
    data = json.loads(request.data) if request.data else {}

    action = data.get('action')
    ids = data['ids']

    for id in ids:
        if action == 'delete':
            ticker = db.session.execute(db.select(Ticker).filter_by(id=id)).scalar()
            if ticker:
                ticker.delete()

    db.session.commit()

    return ''


@admin.route('/tickers', methods=['GET'])
@admin_only
def tickers():
    market = request.args.get('market')
    if not market:
        market = 'crypto'
    return render_template('admin/tickers.html', market=market)


@admin.route('/tickers_detail', methods=['GET'])
@admin_only
def tickers_detail():

    market = request.args['market']
    tickers = tuple(get_tickers(market))
    price_list = get_price_list()

    result = {"total": len(tickers),
              "totalNotFiltered": len(tickers),
              "rows": []}

    for ticker in tickers:
        modal = '<span class="open-modal" data-modal-id="TickerSettingsModal"'
        modal += ' data-url="' + url_for('.ticker_settings', market=market, ticker_id=ticker.id) + '">'
        modal += ticker.id + '</span>'
         
        t = {"checkbox": '<input class="form-check-input to-check" type="checkbox" value="' + ticker.id + '">',
             "id": modal,
             "symbol": ticker.symbol,
             "name": ticker.name,
             "price": price_list.get(ticker.id, 0)}
        if ticker.market_cap_rank:
            t['market_cap_rank'] = ticker.market_cap_rank
        result['rows'].append(t)

    return result


@admin.route('/tickers/settings', methods=['GET'])
@admin_only
def ticker_settings():
    ticker = db.session.execute(
        db.select(Ticker).filter_by(market=request.args.get('market'),
                                    id=request.args.get('ticker_id'))).scalar()
    return render_template('admin/ticker_settings.html', ticker=ticker)


@admin.route('/tickers/settings_update', methods=['POST'])
@admin_only
def ticker_settings_update():
    ticker = db.session.execute(
        db.select(Ticker).filter_by(market=request.args.get('market'),
                                    id=request.args.get('ticker_id'))).scalar()

    ticker.id = request.form.get('id')
    ticker.symbol = request.form.get('symbol')
    ticker.name = request.form.get('name')
    ticker.stable = bool(request.form.get('stable'))

    db.session.commit()
    return ''


@admin.route('/active_tasks', methods=['GET'])
@admin_only
def active_tasks():
    i = celery.control.inspect()
    tasks_list = i.active()
    scheduled = i.scheduled()

    return render_template('admin/active_tasks.html',
                           tasks_list=tasks_list,
                           scheduled=scheduled)


@admin.route('/active_tasks_action/<string:task_id>', methods=['GET'])
@admin_only
def active_tasks_action(task_id):
    celery.control.revoke(task_id, terminate=True)
    return redirect(url_for('.active_tasks'))


@celery.task(bind=True, name='load_stocks_images')
def load_stocks_images(self):
    self.update_state(state='LOADING')
    print('Start load stocks images')
    key = 'apiKey=' + app.config['API_KEY_POLYGON']

    tickers = db.session.execute(
        db.select(Ticker).filter(Ticker.market == 'stocks',
                                 Ticker.image == None)).scalars()

    for ticker in tickers:
        id = ticker.id.upper()
        url = 'https://api.polygon.io/v3/reference/tickers/' + id + '?' + key
        time.sleep(15)
        try:
            r = requests.get(url)
            result = r.json()
            url = result['results']['branding']['icon_url'] + '?' + key
        except:
            return None
        time.sleep(15)
        ticker.image = load_ticker_image(url, 'stocks', id)
        db.session.commit()


@celery.task(bind=True, name='load_crypto_tickers')
def load_crypto_tickers(self):
    ''' загрузка тикеров с https://www.coingecko.com/ru/api/ '''
    self.update_state(state='LOADING')
    print('Load crypto tickers')

    tickers = tuple(get_tickers('crypto'))
    prefix = app.config['CRYPTO_PREFIX']

    def ticker_in_base(id):
        for ticker in tickers:
            if ticker.id == id:
                return ticker
        return None

    page = 1
    new_tickers = {}
    query = True
    while query != []:
        try:
            query = cg.get_coins_markets('usd', per_page='200', page=page)
            query[0]['id']
            print('Crypto page ' + str(page))
        except:
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
                    image=load_ticker_image(coin.get('image'), 'crypto', id)
                )
                db.session.add(ticker)
                new_tickers[id] = 0

            elif not ticker.image:
                ticker.image = load_ticker_image(coin.get('image'), 'crypto', id)

            ticker.market_cap_rank = coin.get('market_cap_rank')

        db.session.commit()

        page += 1
        time.sleep(10)

    print('crypto end')


@celery.task(bind=True, name='load_stocks_tickers')
def load_stocks_tickers(self):
    ''' загрузка тикеров с https://polygon.io/ '''
    self.update_state(state='LOADING')
    print('Load stocks tickers')

    key = 'apiKey=' + app.config['API_KEY_POLYGON']
    tickers = get_tickers('stocks')
    tickers_in_base = [ticker.id for ticker in tickers]
    prefix = app.config['STOCKS_PREFIX']
    new_tickers = False

    date = datetime.now().date()
    url = 'https://api.polygon.io/v3/reference/tickers?market=stocks&date=' + \
        str(date) + '&active=true&order=asc&limit=1000&' + key 

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
        url = next_url + '&' + key if next_url else None
        print('Stocks next url')
        time.sleep(15)

    if new_tickers:
        redis.delete(*['update_stocks'])
    print('stocks tickers end')


@celery.task(bind=True, name='load_currency_tickers')
def load_currency_tickers(self):
    ''' загрузка тикеров с https://currencylayer.com '''
    self.update_state(state='LOADING')
    print('Load currency tickers')

    key = 'access_key=' + app.config['API_KEY_CURRENCYLAYER']
    prefix = app.config['CURRENCY_PREFIX']
    tickers_in_base = [ticker.id for ticker in get_tickers('currency')]
    new_tickers = False

    url = 'http://api.currencylayer.com/list?' + key 

    response = requests.get(url)
    data = response.json()
    while not data['success'] == True:
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


def load_ticker_image(url, market, ticker_id):
    path = app.config['UPLOAD_FOLDER'] + '/images/tickers/' + market
    os.makedirs(path, exist_ok=True)

    try:
        r = requests.get(url)
        original_img = Image.open(BytesIO(r.content))
        filename = (ticker_id + '.' + original_img.format).lower()
    except:
        return None

    def resize_image(px):
        size = (px, px)
        path_local = os.path.join(path, str(px))
        os.makedirs(path_local, exist_ok=True)
        path_saved = os.path.join(path_local, filename)
        original_img.crop((20, 0, 60, 40)).resize(size).save(path_saved)

    resize_image(24)
    resize_image(40)

    return filename


@celery.task(bind=True, name='price_list_crypto', default_retry_delay=0,
             max_retries=None, ignore_result=True)
def price_list_crypto_def(self):
    ''' Запрос цен у КоинГеко криптовалюта '''
    self.update_state(state='WORK')

    prefix = app.config['CRYPTO_PREFIX']
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
            except:
                print("Соединение отклонено сервером... Сплю. ZZzzzz")
                time.sleep(15)

        for id in data:
            price_list[prefix + id] = data[id].get('usd', 0)

        if price_list:
            redis.set('price_list_crypto', pickle.dumps(price_list))
        time.sleep(17)

    # if price_list:
    #     redis.set('price_list_crypto', pickle.dumps(price_list))

    print("End load crypto price")
    price_list_crypto_def.retry()


@celery.task(bind=True, name='price_list_stocks', default_retry_delay=300,
             max_retries=None, ignore_result=True)
def price_list_stocks_def(self):
    ''' Запрос цен у Polygon фондовый рынок '''
    self.update_state(state='WORK')

    update_stocks = redis_decode_or_other('update-stocks', '')

    if update_stocks == str(datetime.now().date()):
        price_list_stocks_def.retry()
        return ''

    price_list = get_price_list('stocks')
    key = 'apiKey=' + app.config['API_KEY_POLYGON']
    prefix = app.config['STOCKS_PREFIX']

    day = 0
    data = {}
    while not data.get('results'):
        day += 1
        # задержка на бесплатном тарифе
        if day % 4 == 0:
            time.sleep(60)

        date = datetime.now().date() - timedelta(days=day)
        url = 'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/' + \
            str(date) + '?adjusted=true&include_otc=false&' + key
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
    price_list_stocks_def.retry()


@celery.task(bind=True, name='price_list_currency', default_retry_delay=300,
             max_retries=None, ignore_result=True)
def price_list_currency_def(self):
    ''' Запрос цен валюты '''
    self.update_state(state='WORK')

    update_currency = redis_decode_or_other('update-currency', '')

    if update_currency == str(datetime.now().date()):
        price_list_stocks_def.retry()
        return ''

    price_list = get_price_list('currency')
    key = 'access_key=' + app.config['API_KEY_CURRENCYLAYER']
    prefix = app.config['CURRENCY_PREFIX']

    url = 'http://api.currencylayer.com/live?' + key
    response = requests.get(url)
    data = response.json()
    while not data.get('success') == True:
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
    price_list_stocks_def.retry()


@admin.route('/test', methods=['GET'])
@admin_only
def price_list_currency_def2():

    update = redis_decode_or_other('update-currency', '')
    if update == str(datetime.now().date()):
        # price_list_stocks_def.retry()
        return ''

    price_list = get_price_list('currency')
    key = 'access_key=' + app.config['API_KEY_CURRENCYLAYER']
    prefix = app.config['CURRENCY_PREFIX']

    ids = [ticker.id[len(prefix):] for ticker in get_tickers('currency')]
    ids_str = ','.join(ids)
    url = 'http://apilayer.net/api/live?' + key + '&currencies=' + ids_str + '&source=USD&format=1'

    response = requests.get(url)
    data = response.json()

    result = []
    if data.get('quotes'):
        price_list[prefix + 'usd'] = 1
        for ticker in data['quotes']:
            id = ticker[3:].lower()
            price_list[prefix + id] = 1 / data['quotes'][ticker]

        if price_list:
            redis.set('update-currency', str(datetime.now().date()))
            redis.set('price_list_currency', pickle.dumps(price_list))

        # print("End load currency price")
        # price_list_stocks_def.retry()
    return result


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


def clear():
    # items = db.session.execute(db.select(WalletTransaction)).scalars()
    # for item in items:
    #     db.session.delete(item)

    items = db.session.execute(db.select(WalletAsset)).scalars()
    for item in items:
        db.session.delete(item)

    items = db.session.execute(db.select(Wallet)).scalars()
    for item in items:
        db.session.delete(item)

    items = db.session.execute(db.select(Asset)).scalars()
    for item in items:
        db.session.delete(item)

    items = db.session.execute(db.select(Portfolio)).scalars()
    for item in items:
        db.session.delete(item)
    db.session.commit()

    items = db.session.execute(db.select(Transaction)).scalars()
    for item in items:
        db.session.delete(item)
    db.session.commit()



@admin.route('/cur', methods=['GET'])
def cur():
    tickers = db.session.execute(
        db.select(Ticker)
        .filter(Ticker.market == 'currency',
        # )
        Ticker.image == None)
    ).scalars()

    path = app.config['UPLOAD_FOLDER'] + '/images/tickers/currency'
    os.makedirs(path, exist_ok=True)

    def load_image(id):
        url = 'http://localhost:5000/admin/p/' + id
        try:
            r = requests.get(url)
            original_img = Image.open(BytesIO(r.content))
            filename = (id + '.' + original_img.format).lower()
        except:
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


    for ticker in tickers:
        ticker.image = load_image(ticker.id[3:])

        db.session.commit()
    return 'Ok'


@admin.route('/curl', methods=['GET'])
def curl():
    tickers = db.session.execute(
        db.select(Ticker)
        .filter(Ticker.market == 'currency',
        # )
        Ticker.image == None)
    ).scalars()

    result = []
    for ticker in tickers:
        result.append({
            'id': ticker.id,
            'name': ticker.name
        })
    leng = len(result)
    result.append({ 'Записей': leng })
    return result


@admin.route('/p/<string:ticker_id>', methods=['GET'])
def p(ticker_id):
    # http://localhost:5000/static/images/temp/cu-cad.png
    path = url_for("static", filename="images/temp/" + ticker_id + ".png")
    return redirect(path)


@admin.route('/curh', methods=['GET'])
def curh():
    load_currency_history.delay()
    return 'Start'


@celery.task()
def load_currency_history():
    key = 'access_key=' + app.config['API_KEY_CURRENCYLAYER']
    prefix = app.config['CURRENCY_PREFIX']

    tickers = tuple(get_tickers('currency'))

    url = 'http://api.currencylayer.com/historical?' + key + '&date='


    def get_ticker(id):
        for ticker in tickers:
            if ticker.id == id:
                return ticker
        return None

    def get_data(date):
        response = requests.get(url + str(date))
        return response.json()


    day = 1
    history = True
    while history:
        day += 1
        date = datetime.now().date() - timedelta(days=day)
        history = db.session.execute(db.select(PriceHistory).filter_by(date=date)).scalar()
        print(date, ' history', bool(history))

    n = 0
    while n <= 300:
        date = date - timedelta(days=1)
        data = get_data(date)
        while not data.get('success') == True:
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
                    db.select(PriceHistory).filter_by(date=date,
                                                      ticker_id=ticker_in_base.id)).scalar()
                if ticker_history:
                    continue
                new_history = PriceHistory(date=date,
                                           ticker_id=ticker_in_base.id,
                                           price_usd=1 / data['quotes'][ticker])
                db.session.add(new_history)

        db.session.commit()
        print(str(date), ' loaded. Next currency history')
        time.sleep(15)
        n += 1
    print('End currency history')

