import json
import re
from flask import abort, redirect, render_template, url_for, request


from ..app import db, redis
from ..wraps import admin_only
from ..jinja_filters import user_datetime
from ..general_functions import MARKETS, actions_in, when_updated
from ..portfolio.models import Ticker
from ..portfolio.utils import get_ticker
from ..user.utils import find_user_by_id
from .models import ApiKey, ApiTask
from .utils import API_NAMES, api_event, get_all_users, get_api, get_api_key, \
    get_api_task, get_tasks, get_tickers, get_tickers_count, \
    task_action, tasks_trans, api_logging, api_info
from . import bp


@bp.route('/index', methods=['GET'])
@admin_only
def index():
    return redirect(url_for('.api_page'))


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


@bp.route('/tickers/settings', methods=['GET', 'POST'])
@admin_only
def ticker_settings():
    ticker = get_ticker(request.args.get('ticker_id')) or abort(404)
    if request.method == 'POST':
        ticker.edit(request.form)
        return ''
    return render_template('admin/ticker_settings.html', ticker=ticker)


@bp.route('/api', methods=['GET', 'POST'])
@admin_only
def api_page():
    api_name = request.args.get('api_name')
    api = get_api(api_name)

    # Actions
    if request.method == 'POST':
        data = json.loads(request.data)
        if 'delete_keys' in data['action']:
            for key in api.keys:
                if str(key.id) in data['ids']:
                    db.session.delete(key)
        db.session.commit()
        return ''

    return render_template('admin/api.html',
                           api=api, log_categories=api_logging.CATEGORIES)


@bp.route('/api/events', methods=['GET', 'POST'])
@admin_only
def api_event_info():
    api_name = request.args.get('api_name')
    event = request.args.get('event')
    if api_name not in API_NAMES or event not in api_event.EVENTS:
        abort(404)

    if request.method == 'POST':
        data = json.loads(request.data)
        action = data['action']
        if 'delete_all' == action:
            api_event.delete(api_name, event)
        return ''

    ids = []
    data = {}
    for event_name, event_ru in api_event.EVENTS.items():
        data_event = api_event.get(event_name, api_name, dict)
        if data_event:
            data[event_ru] = data_event

        # для списка тикеров
        if event_name == event:
            ids = data[event_ru].keys()

    tickers = db.session.execute(
        db.select(Ticker).filter(Ticker.id.in_(ids))).scalars()

    return render_template('admin/api_event.html', data=data, tickers=tickers,
                           event=event, api_name=api_name,
                           api_events=api_event.EVENTS)


@bp.route('/api/<string:api_name>/settings', methods=['GET', 'POST'])
@admin_only
def api_settings(api_name):
    api = get_api(api_name)

    if request.method == 'POST':
        api.edit(request.form)
        return ''

    return render_template('admin/api_settings.html', api=api)


@bp.route('/api/detail', methods=['GET'])
@admin_only
def api_page_detail():
    api_name_ = request.args.get('api_name')
    result = {'info': [], 'streams': [], 'events': []}

    # Для итерации по api
    api_list = [api_name_] if api_name_ in API_NAMES else API_NAMES
    for api_name in api_list:

        # События
        for event_name in redis.hkeys(api_event.key(api_name)):
            count = len(api_event.get(event_name, api_name))

            event_name = event_name.decode()
            if event_name not in api_event.EVENTS:
                # Удалить устаревшие
                api_event.delete(api_name, event_name)
            result['events'].append({'name': api_event.EVENTS[event_name],
                                     'key': event_name, 'value': f'{count}'})

        # Тикеры
        if len(api_list) > 1:
            result['info'].append({'name': api_name.capitalize()})
        if api_name in MARKETS:
            result['info'].append({'name': 'Количество тикеров',
                                   'value': get_tickers_count(api_name)})

        # Информация
        for info_name in redis.hkeys(api_info.key(api_name)):
            value = api_info.get(info_name, api_name)

            # Если дата
            if re.search(r'\d{4}-\d{2}-\d{2}', value):
                value = when_updated(value)

            result['info'].append({'name': f'{info_name.decode()}',
                                   'value': value})

        # Потоки
        if len(api_list) > 1:
            continue
        api = get_api(api_name)
        for stream in api.streams:
            result['streams'].append(
                {'name': stream.name, 'class': 'text-average',
                 'calls': f'{stream.month_calls} из {api.month_limit or "∞"}',
                 'api_key': f'*{stream.key.api_key[-10:]}' if stream.key else 'без ключа',
                 'called': when_updated(stream.first_call_minute, 'Никогда'),
                 'status': 'Активный' if stream.active else 'Не активный'}
            )

    return result


@bp.route('/api/logs', methods=['GET'])
@admin_only
def api_logs():
    timestamp = request.args.get('timestamp', 0.0, type=float)
    api_name_ = request.args.get('api_name')
    logs = []

    # Для итерации по api
    api_list = [api_name_] if api_name_ in API_NAMES else API_NAMES
    for api_name in api_list:
        logs += api_logging.get(api_name, timestamp)

    if logs:
        logs = sorted(logs, key=lambda log: log.get('timestamp'))
    return logs


@bp.route('/api/logs_delete', methods=['POST'])
@admin_only
def api_logs_delete():
    api_name_ = request.args.get('api_name')

    # Для итерации по api
    api_list = [api_name_] if api_name_ in API_NAMES else API_NAMES
    for api_name in api_list:
        redis.delete(api_logging.key(api_name))

    return redirect(url_for('.api_page', api_name=api_name_))


@bp.route('/api/key_settings/', methods=['GET', 'POST'])
@admin_only
def api_key_settings():
    api = get_api(request.args.get('api_name'))
    key = get_api_key(request.args.get('key_id')
                      ) or ApiKey(api_id=request.args.get('api_id'))

    if request.method == 'POST':
        key.edit(request.form)
        return ''

    return render_template('admin/api_key_settings.html', key=key, api=api)


@bp.route('/api/task_settings', methods=['GET', 'POST'])
@admin_only
def task_settings():
    task_name = request.args.get('task_name')
    api_name = request.args.get('api_name')
    task = get_api_task(task_name) or ApiTask()

    if request.method == 'POST':
        if not task.name:
            task.name = task_name
            db.session.add(task)
        task.edit(request.form, api_name)

        return ''

    return render_template('admin/api_task_settings.html',
                           task_name=task_name,
                           task_ru_name=tasks_trans(task_name),
                           task=task)


@bp.route('/tasks', methods=['GET'])
@admin_only
def tasks():
    filter_by = request.args.get('filter')

    tasks_list = get_tasks()
    if filter_by:
        tasks_list = list(filter(lambda task: filter_by in task['name'],
                                 tasks_list))
    else:
        tasks_list = sorted(tasks_list,
                            key=lambda task: task.get('name'), reverse=True)
    return tasks_list


@bp.route('/tasks_action', methods=['GET'])
@admin_only
def tasks_action():
    action = request.args.get('action') or abort(404)
    task_id = request.args.get('task_id')
    task_name = request.args.get('task_name')
    filter_by = request.args.get('filter')

    tasks_list = get_tasks()
    active_ids = [task['id'] for task in tasks_list if task['id']]

    if task_id or task_name:
        # Конкретная задача
        task_action(active_ids, action, task_id=task_id, task_name=task_name)
    else:
        # Все активные задачи
        for task in tasks_list:
            # Отфильтровываем, если запрос из определенного Api
            if filter_by and filter_by not in task['name']:
                continue
            # Запускать только повторяющиеся (имеющие retry_after)
            api_task = get_api_task(task['name'])
            if not api_task or not api_task.retry_after():
                continue
            task_action(active_ids, action, task_id=task['id'],
                        task_name=task['name'])
    return ''
