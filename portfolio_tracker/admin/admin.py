from flask import flash, render_template, redirect, url_for, request, Blueprint
from flask_login import login_required, current_user
from sqlalchemy import func
import time
from datetime import datetime, timedelta
import pickle
from pycoingecko import CoinGeckoAPI
from celery.result import AsyncResult
from portfolio_tracker.general_functions import price_list_def, redis_decode_or_other, when_updated_def
from portfolio_tracker.models import Market, Ticker, User, Wallet
from portfolio_tracker.users import user_delete_def
from portfolio_tracker.wraps import admin_only

from portfolio_tracker.app import app, db, celery, redis


admin = Blueprint('admin', __name__, template_folder='templates', static_folder='static')
cg = CoinGeckoAPI()


@admin.route('/', methods=['GET'])
@admin_only
def admin_index():
    demo_user = db.session.execute(db.select(User).
                                   filter_by(email='demo')).scalar()
    if not demo_user:
        # demo user
        demo_user = User(email='demo', password='demo')
        db.session.add(demo_user)
        wallet = Wallet(name='Default', user_id=demo_user.id)
        db.session.add(wallet)
        db.session.commit()

    markets = db.session.execute(db.select(Market)).scalar()
    if not markets:
        # маркеты
        db.session.add_all([
           Market(name='Crypto', id='crypto'),
           Market(name='Stocks', id='stocks'),
           Market(name='Other', id='other')
        ])
        db.session.commit()

    return render_template('admin/index.html', crypto_count=0, stocks_count=0,
                           users_count=0, admins_count=0)


@admin.route('/index_detail', methods=['GET'])
@admin_only
def admin_index_detail():
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
            return 'Остановлено'

    crypto_tickers_count = db.session.execute(
        db.select(func.count()).select_from(Ticker).
        filter_by(market_id='crypto')).scalar()

    stocks_tickers_count = db.session.execute(
        db.select(func.count()).select_from(Ticker).
        filter_by(market_id='stocks')).scalar()

    users_count = db.session.execute(db.select(func.count()).
                                     select_from(User)).scalar()

    admins_count = db.session.execute(db.select(func.count()).
                                      select_from(User).
                                      filter_by(type='admin')).scalar()

    task_crypto_tickers = AsyncResult(redis_decode_or_other('crypto_tickers_task_id', ''))
    task_stocks_tickers = AsyncResult(redis_decode_or_other('stocks_tickers_task_id', ''))
    task_crypto_price = AsyncResult(redis_decode_or_other('crypto_price_task_id', ''))
    task_stocks_price = AsyncResult(redis_decode_or_other('stocks_price_task_id', ''))

    return {
        "crypto_tickers_count": crypto_tickers_count,
        "stocks_tickers_count": stocks_tickers_count,
        "users_count": users_count,
        "admins_count": admins_count,

        "task_crypto_tickers_id": task_crypto_tickers.id,
        "task_crypto_tickers_state": state(task_crypto_tickers),
        "task_stocks_tickers_id": task_stocks_tickers.id,
        "task_stocks_tickers_state": state(task_stocks_tickers),

        "task_crypto_price_id": task_crypto_price.id,
        "task_crypto_price_state": state(task_crypto_price),
        "task_stocks_price_id": task_stocks_price.id,
        "task_stocks_price_state": state(task_stocks_price),

        "when_update_crypto": when_updated_def(redis_decode_or_other('update-crypto'), '-'),
        "when_update_stocks": when_updated_def(redis_decode_or_other('update-stocks'), '-')
    }


@admin.route('/users', methods=['GET'])
@admin_only
def admin_users():
    users = db.session.execute(db.select(User)).scalars()
    return render_template('admin/users.html', users=users)


@admin.route('/users/user_to_admin/<string:user_id>', methods=['GET'])
@admin_only
def user_to_admin(user_id):
    user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar()
    user.type = 'admin'
    db.session.commit()
    return redirect(url_for('.admin_users'))


@admin.route('/user/delete/<string:user_id>')
@admin_only
def admin_user_delete(user_id):
    user_delete_def(user_id)
    return redirect(url_for('.admin_users'))


@admin.route('/tickers', methods=['GET'])
@admin_only
def admin_tickers():
    tickers = db.session.execute(db.select(Ticker)).scalars()
    return render_template('admin/tickers.html',
                           tickers=tickers,
                           price_list=price_list_def()
                           )


@admin.route('/load_tickers', methods=['GET'])
@admin_only
def load_tickers_start():
    stop_update_prices()
    redis.set('crypto_tickers_task_id', str(load_crypto_tickers.delay().id))
    redis.set('stocks_tickers_task_id', str(load_stocks_tickers.delay().id))

    return redirect(url_for('.admin_index'))


@admin.route('/load_tickers_stop', methods=['GET'])
@admin_only
def load_tickers_stop():
    c_t_redis = redis.get('crypto_tickers_task_id')
    if c_t_redis:
        celery.control.revoke(c_t_redis.decode(), terminate=True)

    s_t_redis = redis.get('stocks_tickers_task_id')
    if s_t_redis:
        celery.control.revoke(s_t_redis.decode(), terminate=True)
    delete_tasks()

    return redirect(url_for('.admin_index'))

@admin.route('/active_tasks', methods=['GET'])
@admin_only
def admin_active_tasks():
    i = celery.control.inspect()
    tasks_list = i.active()
    scheduled = i.scheduled()

    return render_template('admin/active_tasks.html',
                           tasks_list=tasks_list,
                           scheduled=scheduled)


def delete_tasks():
    keys = ['crypto_price_task_id', 'stocks_price_task_id', 'alerts_task_id',
            'crypto_tickers_task_id', 'stocks_tickers_task_id']
    redis.delete(*keys)
    k = redis.keys('celery-task-meta-*')
    if k:
        redis.delete(*k)


@admin.route('/del_tasks', methods=['GET'])
@admin_only
def admin_del_tasks():
    delete_tasks()
    return redirect(url_for('.admin_index'))


@admin.route('/del_price_lists', methods=['GET'])
@admin_only
def admin_del_price_lists():
    delete_price_lists()
    return redirect(url_for('.admin_index'))


@admin.route('/del_alerts', methods=['GET'])
@admin_only
def admin_del_alerts():
    delete_alerts()
    return redirect(url_for('.admin_index'))


@admin.route('/del_all', methods=['GET'])
@admin_only
def admin_del_all():
    delete_all_redis()
    return redirect(url_for('.admin_index'))


@admin.route('/update_prices', methods=['GET'])
@admin_only
def admin_update_prices():
    start_update_prices()
    return redirect(url_for('.admin_index'))


@admin.route('/stop', methods=['GET'])
@admin_only
def admin_update_prices_stop():
    stop_update_prices()
    return redirect(url_for('.admin_index'))


def delete_price_lists():
    keys = ['price_list_crypto', 'price_list_stocks', 'update-crypto',
            'update-stocks']
    redis.delete(*keys)


def delete_alerts():
    keys = ['worked_alerts', 'not_worked_alerts']
    redis.delete(*keys)


def delete_all_redis():
    keys = redis.keys('*')
    redis.delete(*keys)


def start_update_prices():
    redis.set('crypto_price_task_id', str(price_list_crypto_def.delay().id))
    redis.set('stocks_price_task_id', str(price_list_stocks_def.delay().id))
    redis.set('alerts_task_id', str(alerts_update_def.delay().id))


def stop_update_prices():
    crypto_id = redis.get('crypto_price_task_id')
    if crypto_id:
        crypto_id = crypto_id.decode()
        celery.control.revoke(crypto_id, terminate=True)

    stocks_id = redis.get('stocks_price_task_id')
    if stocks_id:
        stocks_id = stocks_id.decode()
        celery.control.revoke(stocks_id, terminate=True)

    alerts_id = redis.get('alerts_task_id')
    if alerts_id:
        alerts_id = alerts_id.decode()
        celery.control.revoke(alerts_id, terminate=True)

    delete_tasks()


@celery.task(bind=True, name='load_crypto_tickers')
def load_crypto_tickers(self):
    ''' загрузка тикеров с https://www.coingecko.com/ru/api/ '''
    self.update_state(state='LOADING')
    print('Load crypto tickers')
    page = 1
    tickers = db.session.execute(
            db.select(Ticker).filter_by(market_id='crypto')).scalars()

    tickers_list = []
    for ticker in tickers:
        tickers_list.append(ticker.id)

    new_tickers = {}
    coins_list_markets = True
    while coins_list_markets != []:
        coins_list_markets = cg.get_coins_markets(
            'usd', per_page='200', page=page)
        print('Crypto page ' + str(page))

        try:
            if coins_list_markets['status'].get('error_code'):
                print('sleep 15 sec')
                time.sleep(15)
                continue
        except:
            pass

        if coins_list_markets != []:
            for coin in coins_list_markets:
                if 'c-' + coin['id'].lower() not in tickers_list:
                    new_ticker = Ticker(
                        id='c-' + coin['id'].lower(),
                        name=coin['name'],
                        symbol=coin['symbol'],
                        market_cap_rank=coin['market_cap_rank'],
                        market_id='crypto',
                        image=coin['image']
                    )
                    tickers_list.append(new_ticker.id)
                    new_tickers[new_ticker.id] = 0
                    db.session.add(new_ticker)
            db.session.commit()

            page += 1
            time.sleep(10)

    # Добавить новые тикеры в прайс
    if new_tickers:
        crypto_redis = redis.get('price_list_crypto')
        price_list = pickle.loads(crypto_redis) if crypto_redis else {}
        price_list = price_list | new_tickers
        redis.set('price_list_crypto', pickle.dumps(price_list))

    print('crypto end')


@celery.task(bind=True, name='load_stocks_tickers')
def load_stocks_tickers(self):
    ''' загрузка тикеров с https://polygon.io/ '''
    self.update_state(state='LOADING')
    print('Load stocks tickers')
    tickers_in_base = db.session.execute(
        db.select(Ticker).filter_by(market_id='stocks')).scalars()
    tickers_list = []
    new_tickers = {}
    for ticker in tickers_in_base:
        tickers_list.append(ticker.id)

    date = datetime.now().date()
    url = 'https://api.polygon.io/v3/reference/tickers?market=stocks&date=' + \
        str(date) + '&active=true&order=asc&limit=1000&apiKey=' + \
        app.config['API_KEY_POLYGON']

    while url:
        response = requests.get(str(url))
        data = response.json()
        if data.get('results'):
            for ticker in data['results']:
                if 's-' + ticker['ticker'].lower() not in tickers_list:
                    new_ticker = Ticker(
                        id='s-' + ticker['ticker'].lower(),
                        name=ticker['name'],
                        symbol=ticker['ticker'],
                        market_id='stocks'
                    )
                    tickers_list.append(new_ticker.id)
                    new_tickers[new_ticker.id] = 0
                    db.session.add(new_ticker)
            db.session.commit()

            url = str(data.get('next_url')) + '&apiKey=' + \
                str(app.config['API_KEY_POLYGON']
                    ) if data.get('next_url') else {}
            print('Stocks next url')
            time.sleep(15)
        else:
            print(data)

    # Добавить новые тикеры в прайс
    if new_tickers:
        stocks_redis = redis.get('price_list_stocks')
        price_list = pickle.loads(stocks_redis) if stocks_redis else {}
        price_list = price_list | new_tickers
        redis.set('price_list_stocks', pickle.dumps(price_list))
        # Чтобы прайс обновился
        redis.delete(*['update_stocks'])
    print('stocks end')


@celery.task(bind=True, name='price_list_crypto', default_retry_delay=0,
             max_retries=None, ignore_result=True)
def price_list_crypto_def(self):
    ''' Запрос цен у КоинГеко криптовалюта '''
    self.update_state(state='WORK')
    crypto_redis = redis.get('price_list_crypto')
    price_list = pickle.loads(crypto_redis) if crypto_redis else {}

    ids = []
    if price_list == {}:
        market = db.session.execute(db.select(Market).
                                    filter_by(id='crypto')).scalar()
        for ticker in market.tickers:
            ids.append(ticker.id[2:])
    else:
        for ticker in list(price_list.keys()):
            ids.append(ticker[2:])

    # Делаем запросы кусками
    max = 1900
    n = 0
    while ids:
        page = ','.join(ids)
        next_page = page[n:max + n]
        poz = next_page.rfind(',')
        if next_page != '' and poz == -1:
            data = cg.get_price(vs_currencies='usd', ids=next_page)
            break
        elif next_page == '':
            break
        else:
            data = ''
            while data == '':
                try:
                    data = cg.get_price(vs_currencies='usd',
                                        ids=next_page[0:poz])
                    n += poz + 1
                    break
                except:
                    print("Соединение отклонено сервером... Сплю. ZZzzzz")
                    time.sleep(15)
                    continue
        if data:
            new_price_list = {}
            for ticker in data:
                new_price_list['c-' + str(ticker)] = data[ticker].get('usd')
            price_list = price_list | new_price_list
        time.sleep(17)
        print('crypto new call')

    if price_list:
        redis.set('update-crypto', str(datetime.now()))
        redis.set('price_list_crypto', pickle.dumps(price_list))
    print("Stop load crypto price")
    price_list_crypto_def.retry()


@celery.task(bind=True, name='price_list_stocks', default_retry_delay=300,
             max_retries=None, ignore_result=True)
def price_list_stocks_def(self):
    ''' Запрос цен у Polygon фондовый рынок '''
    self.update_state(state='WORK')
    stocks_redis = redis.get('price_list_stocks')
    price_list = pickle.loads(stocks_redis) if stocks_redis else {}
    update_redis = redis.get('update-stocks')
    update_stocks = update_redis.decode() if update_redis else ''
    if update_stocks != str(datetime.now().date()):
        day = 1
        while price_list == {}:
            date = datetime.now().date() - timedelta(days=day)
            url = 'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/' + \
                str(date) + '?adjusted=true&include_otc=false&apiKey=' + \
                app.config['API_KEY_POLYGON']
            response = requests.get(url)
            data = response.json()
            if data.get('results'):
                for ticker in data['results']:
                    # вчерашняя цена закрытия, т.к. бесплатно
                    price_list['s-' + ticker['T'].lower()] = ticker['c']
            else:
                # если нет результата, делаем запрос еще на 1 день раньше
                day += 1
                k = day % 4
                # задержка на бесплатном тарифе
                if k == 0:
                    time.sleep(60)

        if price_list:
            redis.set('update-stocks', str(datetime.now().date()))
            redis.set('price_list_stocks', pickle.dumps(price_list))
        print("Stop load stocks price")
    price_list_stocks_def.retry()


@celery.task(bind=True, name='alerts_update', default_retry_delay=180,
             max_retries=None, ignore_result=True)
def alerts_update_def(self):
    ''' Функция собирает уведомления и проверяет нет ли сработавших '''
    self.update_state(state='WORK')
    crypto_redis = redis.get('price_list_crypto')
    price_list_crypto = pickle.loads(crypto_redis) if crypto_redis else {}
    stocks_redis = redis.get('price_list_stocks')
    price_list_stocks = pickle.loads(stocks_redis) if stocks_redis else {}
    price_list = price_list_crypto | price_list_stocks
    flag = False
    not_worked_alerts = redis.get('not_worked_alerts')
    # первый запрос уведомлений
    if not_worked_alerts is None:
        not_worked_alerts = {}
        worked_alerts = {}

        tracked_tickers = db.session.execute(
            db.select(Trackedticker)).scalars()
        for ticker in tracked_tickers:
            if price_list.get(ticker.ticker_id):
                worked_alerts[ticker.user_id] = []
                for alert in ticker.alerts:
                    if alert.worked is False:
                        break
                    price = float(price_list[ticker.ticker_id])
                    if ((alert.type == 'down' and price <= alert.price)
                            or (alert.type == 'up' and price >= alert.price)):
                        alert.worked = True
                        flag = True

                    # если это сработавшее уведомление
                    if alert.worked:
                        a = {}
                        a['id'] = alert.id
                        a['price'] = number_group(smart_round(alert.price))
                        a['type'] = \
                            'упал до ' if alert.type == 'down' else 'вырос до '
                        a['comment'] = alert.comment
                        a['ticker'] = alert.trackedticker.ticker.name
                        if alert.asset_id:
                            a['link'] = \
                                    {'source': 'portfolio',
                                     'market_id': alert.asset.portfolio.market_id,
                                     'portfolio_url': alert.asset.portfolio.url,
                                     'asset_url': alert.trackedticker.ticker_id}
                            a['link_for'] = alert.asset.portfolio.name
                        else:
                            a['link'] = \
                                    {'source': 'tracking_list',
                                     'market_id': alert.trackedticker.ticker.market_id,
                                     'ticker_id': alert.trackedticker.ticker_id}
                            a['link_for'] = 'Список отслеживания'

                        worked_alerts[ticker.user_id].append(a)
                    # если это не сработавшее уведомление
                    if not alert.worked:
                        not_worked_alerts[alert.id] = {}
                        not_worked_alerts[alert.id]['type'] = alert.type
                        not_worked_alerts[alert.id]['price'] = alert.price
                        not_worked_alerts[alert.id]['ticker_id'] = \
                            ticker.ticker_id

        redis.set('worked_alerts', pickle.dumps(worked_alerts))
        redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))

    # последующие запросы уведомлений без запроса в базу
    else:
        alerts_redis = redis.get('not_worked_alerts')
        not_worked_alerts = pickle.loads(alerts_redis) if alerts_redis else {}
        alerts_redis = redis.get('worked_alerts')
        worked_alerts = pickle.loads(alerts_redis) if alerts_redis else {}

        if not_worked_alerts != {}:
            for alert in list(not_worked_alerts.keys()):
                if price_list.get(not_worked_alerts[alert]['ticker_id']):
                    a = not_worked_alerts[alert]
                    price = price_list[a['ticker_id']]
                    if ((a['type'] == 'down' and price <= a['price'])
                            or (a['type'] == 'up' and price >= a['price'])):
                        alert_in_base = db.session.execute(
                            db.select(Alert).filter_by(id=alert)).scalar()
                        alert_in_base.worked = True
                        flag = True
                        # удаляем из несработавших
                        not_worked_alerts.pop(alert, None)
                        # добавляем в сработавшие
                        user_id = alert_in_base.trackedticker.user_id
                        if not worked_alerts.get(user_id):
                            worked_alerts[user_id] = []

                        a = {}
                        a['id'] = alert_in_base.id
                        a['price'] = number_group(
                            smart_round(alert_in_base.price))
                        a['type'] = \
                            'упал до ' if alert_in_base.type == 'down' else 'вырос до '
                        a['comment'] = alert_in_base.comment
                        a['order'] = True if a['comment'] == 'Ордер' else False
                        a['ticker'] = alert_in_base.trackedticker.ticker.name
                        if alert_in_base.asset_id:
                            a['link'] = \
                                    {'source': 'portfolio',
                                     'market_id': alert_in_base.asset.portfolio.market_id,
                                     'portfolio_url': alert_in_base.asset.portfolio.url,
                                     'asset_url': alert_in_base.trackedticker.ticker_id}
                            a['link_for'] = alert_in_base.asset.portfolio.name
                        else:
                            a['link'] = \
                                    {'source': 'tracking_list',
                                     'market_id': alert_in_base.trackedticker.ticker.market_id,
                                     'ticker_id': alert_in_base.trackedticker.ticker_id}
                            a['link_for'] = 'Список отслеживания'

                        worked_alerts[user_id].append(a)

    if flag:
        redis.set('worked_alerts', pickle.dumps(worked_alerts))
        redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))
        db.session.commit()
    alerts_update_def.retry()
