import json
from flask import render_template, redirect, url_for, request
from celery.result import AsyncResult

from portfolio_tracker.admin.utils import get_ticker, get_tickers, \
    get_tickers_count, get_user, get_users_count, task_state
from portfolio_tracker.general_functions import get_price_list, redis_decode, \
    when_updated
from portfolio_tracker.models import User
from portfolio_tracker.wraps import admin_only
from portfolio_tracker.app import db, celery, redis
from portfolio_tracker.admin import bp
from portfolio_tracker.admin.tasks import alerts_update, crypto_tickers, \
    currency_tickers, load_stocks_images, prices_crypto, prices_currency, \
    prices_stocks, stocks_tickers


@bp.route('/', methods=['GET'])
@admin_only
def index():
    return render_template('admin/index.html')


@bp.route('/index_detail', methods=['GET'])
@admin_only
def index_detail():
    crypto_tickers = AsyncResult(redis_decode('crypto_tickers_task_id', ''))
    crypto_price = AsyncResult(redis_decode('crypto_price_task_id', ''))
    stocks_tickers = AsyncResult(redis_decode('stocks_tickers_task_id', ''))
    stocks_price = AsyncResult(redis_decode('stocks_price_task_id', ''))
    stocks_image = AsyncResult(redis_decode('stocks_image_task_id', ''))
    alerts = AsyncResult(redis_decode('alerts_task_id', ''))

    currency_tickers = AsyncResult(redis_decode('currency_tickers_task_id', ''))
    currency_price = AsyncResult(redis_decode('currency_price_task_id', ''))

    return {
        "users_count": get_users_count(),
        "admins_count": get_users_count('admin'),
        "task_alerts_id": alerts.id,
        "task_alerts_state": task_state(alerts),
        "crypto": {
            "tickers_count": get_tickers_count('crypto'),
            "task_tickers_id": crypto_tickers.id,
            "task_tickers_state": task_state(crypto_tickers),
            "task_price_id": crypto_price.id,
            "task_price_state": task_state(crypto_price),
            "price_when_update": when_updated(redis_decode('update-crypto'), '-')
        },
        "stocks": {
            "tickers_count": get_tickers_count('stocks'),
            "task_tickers_id": stocks_tickers.id,
            "task_tickers_state": task_state(stocks_tickers),
            "task_price_id": stocks_price.id,
            "task_price_state": task_state(stocks_price),
            "task_image_id": stocks_image.id,
            "task_image_state": task_state(stocks_image),
            "price_when_update": when_updated(redis_decode('update-stocks'), '-')
        },
        "currency": {
            "tickers_count": get_tickers_count('currency'),
            "task_tickers_id": currency_tickers.id,
            "task_tickers_state": task_state(currency_tickers),
            "task_price_id": currency_price.id,
            "task_price_state": task_state(currency_price),
            "price_when_update": when_updated(redis_decode('update-currency'), '-')
        },
    }


@bp.route('/index_action', methods=['GET'])
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
        redis.set('crypto_tickers_task_id', str(crypto_tickers.delay().id))
    elif action == 'stocks_tickers_start':
        task_stop('stocks_tickers_task_id')
        redis.set('stocks_tickers_task_id', str(stocks_tickers.delay().id))
    elif action == 'currency_tickers_start':
        task_stop('currency_tickers_task_id')
        redis.set('currency_tickers_task_id', str(currency_tickers.delay().id))
    if action == 'crypto_price_start':
        task_stop('crypto_price_task_id')
        redis.set('crypto_price_task_id', str(prices_crypto.delay().id))
    elif action == 'stocks_price_start':
        task_stop('stocks_price_task_id')
        redis.set('stocks_price_task_id', str(prices_stocks.delay().id))
    elif action == 'currency_price_start':
        task_stop('currency_price_task_id')
        redis.set('currency_price_task_id', str(prices_currency.delay().id))
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

    return redirect(url_for('.index'))


@bp.route('/users', methods=['GET'])
@admin_only
def users():
    return render_template('admin/users.html')


@bp.route('/users_detail', methods=['GET'])
@admin_only
def users_detail():
    users = tuple(db.session.execute(db.select(User)).scalars())

    result = {"total": len(users),
              "totalNotFiltered": len(users),
              "rows": []}
    for user in users:
        result['rows'].append({
            "id": (f'<input class="form-check-input to-check" type="checkbox" '
                   f'value="{user.id}">'),
            "email": user.email,
            "type": user.type,
            "portfolios": len(user.portfolios),
            "first_visit": user.info.first_visit if user.info else '',
            "last_visit": user.info.last_visit if user.info else '',
            "country": user.info.country if user.info else '',
            "city": user.info.city if user.info else ''
        })

    return result


@bp.route('/users/action', methods=['POST'])
@admin_only
def users_action():
    data = json.loads(request.data) if request.data else {}

    action = data.get('action')
    ids = data['ids']

    for id in ids:
        user = get_user(id)
        if not user:
            continue

        if action == 'user_to_admin':
            user.type = 'admin'
            db.session.commit()
        elif action == 'admin_to_user':
            user.type = ''
            db.session.commit()

        elif action == 'delete':
            user.delete()

    return ''


@bp.route('/imports', methods=['GET'])
@admin_only
def imports():
    return render_template('admin/imports.html')


@bp.route('/tickers/action', methods=['POST'])
@admin_only
def tickers_action():
    data = json.loads(request.data) if request.data else {}

    action = data.get('action')
    ids = data['ids']

    for id in ids:
        ticker = get_ticker(id)
        if not ticker:
            continue

        if action == 'delete':
            ticker.delete()

    db.session.commit()

    return ''


@bp.route('/tickers', methods=['GET'])
@admin_only
def tickers():
    return render_template('admin/tickers.html',
                           market=request.args.get('market', 'crypto'))


@bp.route('/tickers_detail', methods=['GET'])
@admin_only
def tickers_detail():
    tickers = tuple(get_tickers(request.args['market']))
    price_list = get_price_list()

    result = {"total": len(tickers),
              "totalNotFiltered": len(tickers),
              "rows": []}

    for ticker in tickers:
        url = url_for('.ticker_settings', ticker_id=ticker.id)

        result['rows'].append({
            "checkbox": (f'<input class="form-check-input to-check"'
                         f'type="checkbox" value="{ticker.id}">'),
            "id": (f'<span class="open-modal" data-modal-id='
                   f'"TickerModal" data-url={url}>{ticker.id}</span>'),
            "symbol": ticker.symbol,
            "name": ticker.name,
            "price": price_list.get(ticker.id, 0),
            "market_cap_rank": ticker.market_cap_rank or ''
        })

    return result


@bp.route('/tickers/settings', methods=['GET'])
@admin_only
def ticker_settings():
    ticker = get_ticker(request.args.get('ticker_id'))
    return render_template('admin/ticker_settings.html', ticker=ticker)


@bp.route('/tickers/settings_update', methods=['POST'])
@admin_only
def ticker_settings_update():
    ticker = get_ticker(request.args.get('ticker_id'))
    if ticker:
        ticker.edit(request.form)

    return ''


@bp.route('/active_tasks', methods=['GET'])
@admin_only
def active_tasks():
    i = celery.control.inspect()
    tasks_list = i.active()
    scheduled = i.scheduled()

    return render_template('admin/active_tasks.html',
                           tasks_list=tasks_list,
                           scheduled=scheduled)


@bp.route('/active_tasks_action/<string:task_id>', methods=['GET'])
@admin_only
def active_tasks_action(task_id):
    celery.control.revoke(task_id, terminate=True)
    return redirect(url_for('.active_tasks'))
