from flask import render_template, redirect, url_for, request

from ..general_functions import actions_in, redis_decode, when_updated
from ..jinja_filters import user_datetime
from ..wraps import admin_only
from ..app import celery, redis
from ..portfolio.utils import get_ticker
from ..user.utils import find_user_by_id
from .utils import get_all_users, get_task_log, get_tickers, \
    get_tickers_count, get_users_count
from . import bp


@bp.route('/', methods=['GET'])
@admin_only
def index():
    info = {
        "users_count": get_users_count(),
        "admins_count": get_users_count('admin'),
        "crypto_update": when_updated(redis_decode('update-crypto'), 'Нет'),
        "stocks_update": when_updated(redis_decode('update-stocks'), 'Нет'),
        "currency_update": when_updated(redis_decode('update-currency'), 'Нет')
    }
    return render_template('admin/index.html', info=info)


@bp.route('/index_action', methods=['GET'])
@admin_only
def index_action():
    action = request.args.get('action')

    if action == 'redis_delete_all':
        keys = redis.keys('*')
        redis.delete(*keys)

    return redirect(url_for('.index'))


@bp.route('/users', methods=['GET'])
@admin_only
def users_page():
    return render_template('admin/users.html')


@bp.route('/users_detail', methods=['GET'])
@admin_only
def users_detail():
    users = get_all_users()

    result = {"total": len(users),
              "totalNotFiltered": len(users),
              "rows": []}
    for user in users:
        if user.type == 'demo':
            continue

        result['rows'].append({
            "id": (f'<input class="form-check-input to-check" type="checkbox" '
                   f'value="{user.id}">'),
            "email": user.email,
            "type": user.type,
            "portfolios": len(user.portfolios),
            "first_visit": user_datetime(user.info.first_visit),
            "last_visit": user_datetime(user.info.last_visit),
            "country": user.info.country if user.info else '',
            "city": user.info.city if user.info else ''
        })

    return result


@bp.route('/users/action', methods=['POST'])
@admin_only
def users_action():
    actions_in(request.data, find_user_by_id)
    return ''


@bp.route('/imports', methods=['GET'])
@admin_only
def imports():
    return render_template('admin/imports.html')


@bp.route('/tickers/action', methods=['POST'])
@admin_only
def tickers_action():
    actions_in(request.data, get_ticker)
    return ''


@bp.route('/tickers', methods=['GET'])
@admin_only
def tickers_page():
    return render_template('admin/tickers.html',
                           market=request.args.get('market', 'crypto'))


@bp.route('/tickers_detail', methods=['GET'])
@admin_only
def tickers_detail():
    tickers = get_tickers(request.args.get('market'))

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
            "price": ticker.price,
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


@bp.route('/crypto', methods=['GET'])
@admin_only
def crypto():
    return render_template('admin/crypto.html')


@bp.route('/crypto_detail', methods=['GET'])
@admin_only
def crypto_detail():
    return {
        "tickers_count": get_tickers_count('crypto'),
        "price_when_update": when_updated(redis_decode('update-crypto'), 'Нет')
        }


@bp.route('/tasks', methods=['GET'])
@admin_only
def tasks():
    to_filter = request.args.get('filter')

    i = celery.control.inspect()
    active = i.active()
    scheduled = i.scheduled()
    registered = i.registered()

    tasks_list = []
    tasks_names = []
    if active:
        for server in active:
            for task in active[server]:
                tasks_list.append({'name': task['name'],
                                   'task_id': task['id']})
                tasks_names.append(task['name'])

    if scheduled:
        for server in scheduled:
            for task in scheduled[server]:
                tasks_list.append({'name': task['request']['name'],
                                   'task_id': task['request']['id']})
                tasks_names.append(task['request']['name'])

    if registered:
        for server in registered:
            for task in registered[server]:
                if task not in tasks_names:
                    tasks_list.append({'name': task, 'task_id': ''})

    if to_filter:
        tasks_list = list(filter(lambda task: to_filter in task['name'],
                                 tasks_list))
    return tasks_list


@bp.route('/crypto_logs', methods=['GET'])
@admin_only
def crypto_logs():
    logs = get_task_log('crypto')
    loaded_logs_count = request.args.get('loaded_logs_count', 0, type=int)

    if len(logs) - loaded_logs_count > 0:
        logs = sorted(logs, key=lambda log: log.get('time'))
        return logs[loaded_logs_count:]

    return []


@bp.route('/tasks_action', methods=['GET'])
@admin_only
def tasks_action():
    action = request.args.get('action')
    task = request.args.get('task')

    if action and task:
        if action == 'stop':
            celery.control.revoke(task, terminate=True)

        elif action == 'start':
            task = celery.signature(task)
            task.delay()

    return ''
