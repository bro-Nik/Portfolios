from pycoingecko import CoinGeckoAPI
import os, json, requests, time
from datetime import datetime, timedelta
from celery.schedules import crontab
import pickle

from portfolio_tracker.app import app, db, celery, redis
from portfolio_tracker.models import Transaction, Asset, Wallet, Portfolio, Ticker, Market, Alert, Trackedticker


cg = CoinGeckoAPI()
date = datetime.now().date()


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    price_list_crypto_def.delay()
    #sender.add_periodic_task(float(app.config['CRYPTO_UPDATE']), price_list_crypto_def.s())
    sender.add_periodic_task(300, price_list_stocks_def.s())
    pass


def price_list_def():
    ''' Общая функция сбора цен '''
    price_list_crypto = pickle.loads(redis.get('price_list_crypto')) if redis.get('price_list_crypto') else {}
    price_list_stocks = pickle.loads(redis.get('price_list_stocks')) if redis.get('price_list_stocks') else {}
    price_list = price_list_crypto | price_list_stocks

    return price_list


@celery.task(default_retry_delay=0, max_retries=None)
def price_list_crypto_def():
    ''' Запрос цен у КоинГеко криптовалюта '''
    start_time = time.time()
    price_list = pickle.loads(redis.get('price_list_crypto')) if redis.get('price_list_crypto') else {}
    if price_list == {}:
        market = db.session.execute(db.select(Market).filter_by(id='crypto')).scalar()
        ids = []
        for ticker in market.tickers:
            if ticker.id:
                ids.append(ticker.id)
    else:
        # берем id тикеров из прайса
        ids = list(price_list.keys())
        if 'update-crypto' in ids:
            ids.remove('update-crypto')
    # Делаем запросы кусками
    max = 1900
    n = 0
    while True:
        str = ','.join(ids)
        next_str = str[n:max + n]
        poz = next_str.rfind(',')
        if next_str != '' and poz == -1:
            data = cg.get_price(vs_currencies='usd', ids=next_str)
            break
        elif next_str == '':
            break
        else:
            data = cg.get_price(vs_currencies='usd', ids=next_str[0:poz])
            n += poz + 1
        if data:
            for ticker in data:
                data[ticker] = data[ticker].get('usd')
        price_list = price_list | data
        time.sleep(15)

    if price_list:
        #price_list['update-crypto'] = str(datetime.now())
        redis.set('price_list_crypto', pickle.dumps(price_list))
    print("Stop load crypto price, %s seconds" % (time.time() - start_time))
    alerts_update_def.delay()
    price_list_crypto_def.retry()


@celery.task
def price_list_stocks_def():
    ''' Запрос цен у Polygon фондовый рынок '''
    price_list = pickle.loads(redis.get('price_list_stocks')) if redis.get('price_list_stocks') else {}
    if price_list.get('update-stocks') != str(datetime.now().date()):
        start_time = time.time()
        day = 1
        while price_list == {}:
            date = datetime.now().date() - timedelta(days=day)
            url = 'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/' + str(date) + '?adjusted=true&include_otc=false&apiKey=' + app.config['API_KEY_POLYGON']
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
                    time.sleep(60)

        if price_list:
            price_list['update-stocks'] = str(datetime.now().date())
            redis.set('price_list_stocks', pickle.dumps(price_list))
            alerts_update_def.delay()
        print("Stop load stocks price, %s seconds" % (time.time() - start_time))

@celery.task
def alerts_update_def():
    ''' Функция собирает уведомления и проверяет нет ли сработавших '''
    price_list_crypto = pickle.loads(redis.get('price_list_crypto')) if redis.get('price_list_crypto') else {}
    price_list_stocks = pickle.loads(redis.get('price_list_stocks')) if redis.get('price_list_stocks') else {}
    price_list = {**price_list_crypto, **price_list_stocks}
    flag = False
    not_worked_alerts = redis.get('not_worked_alerts')
    # первый запрос уведомлений
    if not_worked_alerts is None:
        not_worked_alerts = {}
        worked_alerts = {}

        tracked_tickers = db.session.execute(db.select(Trackedticker)).scalars()
        for ticker in tracked_tickers:
            worked_alerts[ticker.user_id] = []
            for alert in ticker.alerts:
                if alert.worked == False:
                    break
                if (alert.type == 'down' and float(price_list[ticker.ticker_id]) <= alert.price) or (alert.type == 'up' and float(price_list[ticker.ticker_id]) >= alert.price):
                    alert.worked = True
                    flag = True

                # если это сработавшее уведомление
                if alert.worked:
                    a = {}
                    a['id'] = alert.id
                    a['price'] = number_group(smart_round(alert.price))
                    a['type'] = 'упал до ' if alert.type == 'down' else 'вырос до '
                    a['comment'] = alert.comment
                    a['ticker'] = alert.trackedticker.ticker.name
                    if alert.asset_id:
                        a['link'] = {'source': 'portfolio', 'market_id': alert.asset.portfolio.market_id, 'portfolio_url': alert.asset.portfolio.url, 'asset_url': alert.trackedticker.ticker_id}
                        a['link_for'] = alert.asset.portfolio.name
                    else:
                        a['link'] = {'source': 'tracking_list', 'market_id': alert.trackedticker.ticker.market_id, 'ticker_id': alert.trackedticker.ticker_id}
                        a['link_for'] = 'Список отслеживания'

                    worked_alerts[ticker.user_id].append(a)
                # если это не сработавшее уведомление
                if not alert.worked:
                    not_worked_alerts[alert.id] = {}
                    not_worked_alerts[alert.id]['type'] = alert.type
                    not_worked_alerts[alert.id]['price'] = alert.price
                    not_worked_alerts[alert.id]['ticker_id'] = ticker.ticker_id
        redis.set('worked_alerts', pickle.dumps(worked_alerts))
        redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))

    # последующие запросы уведомлений без запроса в базу
    else:
        not_worked_alerts = pickle.loads(redis.get('not_worked_alerts')) if redis.get('not_worked_alerts') else {}
        worked_alerts = pickle.loads(redis.get('worked_alerts')) if redis.get('worked_alerts') else {}

        if not_worked_alerts != {}:
            for alert in list(not_worked_alerts.keys()):
                if (not_worked_alerts[alert]['type'] == 'down' and price_list[not_worked_alerts[alert]['ticker_id']] <= not_worked_alerts[alert]['price']) \
                        or (not_worked_alerts[alert]['type'] == 'up' and price_list[not_worked_alerts[alert]['ticker_id']] >= not_worked_alerts[alert]['price']):
                    alert_in_base = db.session.execute(db.select(Alert).filter_by(id=alert)).scalar()
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
                    a['price'] = number_group(smart_round(alert_in_base.price))
                    a['type'] = 'упал до ' if alert_in_base.type == 'down' else 'вырос до '
                    a['comment'] = alert_in_base.comment
                    a['order'] = True if a['comment'] == 'Ордер' else False
                    a['ticker'] = alert_in_base.trackedticker.ticker.name
                    if alert_in_base.asset_id:
                        a['link'] = {'source': 'portfolio', 'market_id': alert_in_base.asset.portfolio.market_id, 'portfolio_url': alert_in_base.asset.portfolio.url, 'asset_url': alert_in_base.trackedticker.ticker_id}
                        a['link_for'] = alert_in_base.asset.portfolio.name
                    else:
                        a['link'] = {'source': 'tracking_list', 'market_id': alert_in_base.trackedticker.ticker.market_id, 'ticker_id': alert_in_base.trackedticker.ticker_id}
                        a['link_for'] = 'Список отслеживания'

                    worked_alerts[user_id].append(a)

    if flag:
        redis.set('worked_alerts', pickle.dumps(worked_alerts))
        redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))
        db.session.commit()


def when_updated_def(when_updated):
    ''' Возвращает сколько прошло от входящей даты '''
    if type(when_updated) == str:
        try:
            when_updated = datetime.strptime(when_updated, '%Y-%m-%d %H:%M:%S.%f')
        except:
            when_updated = datetime.strptime(when_updated + ' 20:00:00.000000', '%Y-%m-%d %H:%M:%S.%f')

    delta_time = datetime.now() - when_updated
    if date == datetime.date(when_updated):
        if delta_time.total_seconds() < 60:
            result = ''
            #result = 'менее минуты'
        elif 60 <= delta_time.total_seconds() < 3600:
            result = str(int(delta_time.total_seconds() / 60)) + ' мин.'
        elif 3600 <= delta_time.total_seconds() < 86400:
            result = str(int(delta_time.total_seconds() / 3600)) + ' ч.'
    elif 0 < (date - datetime.date(when_updated)).days < 2:
        result = 'вчера'
    elif 2 <= (date - datetime.date(when_updated)).days < 10:
        result = str((date - datetime.date(when_updated)).days) + 'д. назад'
    else:
        result = str(datetime.date(when_updated))
    return result

@celery.task
def load_crypto_tickers():
    ''' загрузка тикеров с https://www.coingecko.com/ru/api/ '''
    print('Load crypto tickers')
    page = 1
    #tickers_in_base = db.session.execute(db.select(Ticker).filter_by(market_id='crypto')).scalars()

    #tickers_list = []
    #if tickers_in_base != ():
    #    for ticker in tickers_in_base:
    #        tickers_list.append(ticker.id)

    coins_list_markets = True
    while coins_list_markets != []:
        coins_list_markets = cg.get_coins_markets('usd', per_page='200', page=page)
        print(page)
        try:
            if coins_list_markets['status'].get('error_code'):
                print('sleep 15 sec')
                time.sleep(15)
                continue
        except:
            pass

        if coins_list_markets != []:
            for coin in coins_list_markets:
                t_in_base = db.session.execute(db.select(Ticker).filter_by(id=coin['id'].lower())).scalar()
                #if coin['id'].lower() not in tickers_list and not t:
                if not t_in_base:
                    new_ticker = Ticker(
                        id=coin['id'].lower(),
                        name=coin['name'],
                        symbol=coin['symbol'],
                        market_cap_rank=coin['market_cap_rank'],
                        market_id='crypto',
                        image=coin['image']
                    )
                    #tickers_list.append(new_ticker.id)
                    db.session.add(new_ticker)
            db.session.commit()

            page += 1
            time.sleep(10)
    print('crypto end')


@celery.task
def load_stocks_tickers():
    ''' загрузка тикеров с https://polygon.io/ '''
    print('Load stocks tickers')
    tickers_in_base = db.session.execute(db.select(Ticker).filter_by(market_id='stocks')).scalars()
    tickers_list = []
    if tickers_in_base != ():
        for ticker in tickers_in_base:
            tickers_list.append(ticker.id)
    url = 'https://api.polygon.io/v3/reference/tickers?market=stocks&date=2022-12-30&active=true&order=asc&apiKey=' + app.config['API_KEY_POLYGON']
    while url:
        response = requests.get(url)
        data = response.json()
        if data.get('results'):
            for ticker in data['results']:
                t_in_base = db.session.execute(db.select(Ticker).filter_by(id=ticker['ticker'].lower())).scalar()
                #if ticker['ticker'].lower() not in tickers_list:
                if not t_in_base:
                    new_ticker = Ticker(
                        id=ticker['ticker'].lower(),
                        name=ticker['name'],
                        symbol=ticker['ticker'],
                        market_id='stocks'
                    )
                    #tickers_list.append(new_ticker.id)
                    db.session.add(new_ticker)
            db.session.commit()
            url = str(data.get('next_url')) + '&apiKey=' + str(app.config['API_KEY_POLYGON']) if data.get('next_url') else {}
            print('Stocks next url')
            time.sleep(15)
        else:
            print(data)
    print('stocks end')


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

