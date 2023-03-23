from pycoingecko import CoinGeckoAPI
import json
import requests
import time
from datetime import datetime, timedelta
import pickle

from portfolio_tracker.app import app, db, celery, redis
from portfolio_tracker.models import Ticker, Market, Alert, Trackedticker, Asset


cg = CoinGeckoAPI()


# @celery.on_after_configure.connect
# def setup_periodic_tasks(sender, **kwargs):
#    # sender.add_periodic_task(crontab(hour=0, minute=0), clear_redis.s(),)
#    pass


def price_list_def():
    ''' Общая функция сбора цен '''
    crypto_redis = redis.get('price_list_crypto')
    price_list_crypto = pickle.loads(crypto_redis) if crypto_redis else {}
    stocks_redis = redis.get('price_list_stocks')
    price_list_stocks = pickle.loads(stocks_redis) if stocks_redis else {}

    return price_list_crypto | price_list_stocks


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


def when_updated_def(when_updated):
    ''' Возвращает сколько прошло от входящей даты '''
    if type(when_updated) == str:
        try:
            when_updated = datetime.strptime(
                when_updated, '%Y-%m-%d %H:%M:%S.%f')
        except:
            when_updated = datetime.strptime(
                when_updated + ' 20:00:00.000000', '%Y-%m-%d %H:%M:%S.%f')

    delta_time = datetime.now() - when_updated
    date = datetime.now().date()
    if date == datetime.date(when_updated):
        if delta_time.total_seconds() < 60:
            result = 'менее минуты'
        elif 60 <= delta_time.total_seconds() < 3600:
            result = str(int(delta_time.total_seconds() / 60)) + ' мин.'
        else:
            result = str(int(delta_time.total_seconds() / 3600)) + ' ч.'
    elif 0 < (date - datetime.date(when_updated)).days < 2:
        result = 'вчера'
    elif 2 <= (date - datetime.date(when_updated)).days < 10:
        result = str((date - datetime.date(when_updated)).days) + 'д. назад'
    else:
        result = str(datetime.strftime(when_updated, '%Y-%m-%d %H:%M'))
    return result


def tickers_to_redis(market_id):
    tickers_list = []

    def add_tickers(tickers):
        if tickers != ():
            for ticker in tickers:
                new_ticker = {}
                new_ticker['id'] = ticker.id
                new_ticker['name'] = ticker.name
                new_ticker['symbol'] = ticker.symbol.upper()
                cap_rank = ticker.market_cap_rank
                cap_rank = '#' + str(cap_rank) if cap_rank else ''
                new_ticker['market_cap_rank'] = cap_rank
                new_ticker['image'] = '<img class="img-asset-min" src="' + \
                    ticker.image + '">' if ticker.image else ''
                tickers_list.append(new_ticker)

    tickers_cap = db.session.execute(
            db.select(Ticker).
            filter_by(market_id=market_id).
            filter(Ticker.market_cap_rank != None).
            order_by(Ticker.market_cap_rank)).scalars()
    add_tickers(tickers_cap)

    tickers_not_cap = db.session.execute(
            db.select(Ticker).
            filter_by(market_id=market_id).
            filter(Ticker.market_cap_rank == None).
            order_by(Ticker.symbol)).scalars()
    add_tickers(tickers_not_cap)

    redis.set('tickers-' + market_id, json.dumps(tickers_list))
    return tickers_list


@celery.task(bind=True, name='load_crypto_tickers')
def load_crypto_tickers(self):
    ''' загрузка тикеров с https://www.coingecko.com/ru/api/ '''
    self.update_state(state='LOADING')
    print('Load crypto tickers')
    page = 1
    tickers_in_base = db.session.execute(
            db.select(Ticker).filter_by(market_id='crypto')).scalars()

    tickers_list = []
    if tickers_in_base != ():
        for ticker in tickers_in_base:
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
    redis.delete('tickers-crypto')

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
    if tickers_in_base != ():
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
    redis.delete('tickers-stocks')

    # Добавить новые тикеры в прайс
    if new_tickers:
        stocks_redis = redis.get('price_list_stocks')
        price_list = pickle.loads(stocks_redis) if stocks_redis else {}
        price_list = price_list | new_tickers
        redis.set('price_list_stocks', pickle.dumps(price_list))
        # Чтобы прайс обновился
        redis.delete(*['update_stocks'])
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
    except:  # строка не является float / int
        return ''


app.add_template_filter(smart_round)


def number_group(number):
    ''' Разделитель тысяных для Jinja '''
    return long_number(number) if (0 < number < 0.0005) else '{:,}'.format(number).replace(',', ' ')


app.add_template_filter(number_group)


def long_number(number):
    ''' для Jinja '''
    return '{:.18f}'.format(number).rstrip('0') if number < 0.0005 else number


app.add_template_filter(long_number)
