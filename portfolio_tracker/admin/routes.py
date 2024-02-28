import json
import re
import time
from flask import abort, redirect, render_template, url_for, request

from ..app import db, redis
from ..wraps import admin_only
from ..jinja_filters import user_datetime
from ..general_functions import MARKETS, actions_in, when_updated
from ..portfolio.models import Ticker
from ..portfolio.utils import get_ticker
from ..user.utils import find_user_by_id
from .models import Key, Task
from .api_integration import API_NAMES, ApiIntegration, Event, Log, \
    get_api_task, tasks_trans
from .utils import get_all_users, get_tasks, \
    get_tickers, get_tickers_count, task_action
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
    api = ApiIntegration(api_name).api if api_name else None

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
                           api=api, log_categories=Log.CATEGORIES)


@bp.route('/api/events', methods=['GET'])
@admin_only
def api_event_info():
    event = request.args.get('event')
    if event not in Event.EVENTS:
        abort(404)

    api = ApiIntegration(request.args.get('api_name')) or abort(404)

    ids = []
    data = {}

    # Общие действия
    for event_name, event_name_ru in Event.EVENTS.items():
        data_event = api.events.get(event_name, dict)
        if data_event:
            data[event_name_ru] = data_event

        # для списка тикеров
        if event_name == event:
            ids = data[event_name_ru].keys()

    tickers = db.session.execute(
        db.select(Ticker).filter(Ticker.id.in_(ids))).scalars()

    return render_template('admin/api_event.html', data=data, tickers=tickers,
                           event=event, api_name=api.api.name,
                           api_events=Event.EVENTS)


@bp.route('/api/events', methods=['POST'])
@admin_only
def api_event_action():
    # event = request.args.get('event')
    # if event not in Event.EVENTS:
    #     abort(404)
    #
    # api = ApiIntegration(request.args.get('api_name')) or abort(404)

    # if 'delete_all_redis' == action:
    #     api.events.delete(event)
    # else:
    actions_in(request.data, get_ticker)
    return ''


@bp.route('/api/<string:api_name>/settings', methods=['GET', 'POST'])
@admin_only
def api_settings(api_name):
    module = ApiIntegration(api_name)
    api = module.api

    if request.method == 'POST':
        api.edit(request.form)
        # Обновляем потоки
        module.update_streams()
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
        api = ApiIntegration(api_name)

        # События
        events_list = []
        for event_name in redis.hkeys(api.events.key):
            count = len(api.events.get(event_name))

            event_name = event_name.decode()
            if event_name not in Event.EVENTS:
                # Удалить устаревшие
                api.events.delete(event_name)
            events_list.append({'name': Event.EVENTS[event_name],
                                'key': event_name, 'value': f'{count}'})

        # Заголовок в событиях
        if len(api_list) > 1 and events_list:
            result['events'].append({'group_name': api.api.name.capitalize()})
        result['events'] += events_list

        info_list = []

        # Тикеры
        if api_name in MARKETS:
            info_list.append({'name': 'Количество тикеров',
                              'value': get_tickers_count(api.api.name)})

        # Информация
        for info_name in redis.hkeys(api.info.key):
            value = api.info.get(info_name)
            # print(value)

            # Если дата
            if re.search(r'\d{4}-\d{2}-\d{2}', value):
                value = when_updated(value)

            info_list.append({'name': f'{info_name.decode()}',
                              'value': value})

        # Заголовок в информации
        if len(api_list) > 1 and info_list:
            result['info'].append({'group_name': api_name.capitalize()})
        result['info'] += info_list

        # Потоки
        if len(api_list) > 1:
            continue
        # api = get_api(api_name)
        for stream in api.api.streams:
            result['streams'].append(
                {'name': stream.name, 'class': 'text-average',
                 'calls': f'{stream.month_calls} из {api.api.month_limit or "∞"}',
                 'api_key': f'*{stream.key.api_key[-10:]}' if stream.key else 'без ключа',
                 'called': when_updated(stream.next_call, 'Никогда'),
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
        api = ApiIntegration(api_name)
        logs += api.logs.get(timestamp)

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
        api = ApiIntegration(api_name)
        redis.delete(api.logs.key)

    return redirect(url_for('.api_page', api_name=api_name_))


@bp.route('/api/key_settings/', methods=['GET', 'POST'])
@admin_only
def api_key_settings():
    module = ApiIntegration(request.args.get('api_name'))
    api = module.api

    key = db.session.execute(
        db.select(Key).filter_by(id=request.args.get('key_id'))
    ).scalar() or Key(api_id=api.id)

    if request.method == 'POST':
        key.edit(request.form)
        # Обновляем потоки
        module.update_streams()
        return ''

    return render_template('admin/api_key_settings.html', key=key, api=api)


@bp.route('/api/task_settings', methods=['GET', 'POST'])
@admin_only
def task_settings():
    task_name = request.args.get('task_name')
    task = get_api_task(task_name) or Task()

    if request.method == 'POST':
        if not task.name:
            task.name = task_name
            db.session.add(task)
        task.edit(request.form)

        return ''

    return render_template('admin/api_task_settings.html',
                           task_name=task_name,
                           task_ru_name=tasks_trans(task_name),
                           task=task)


@bp.route('/tasks', methods=['GET'])
@admin_only
def tasks():
    tasks_list = get_tasks()
    result = []

    # Задачи определенного Api
    filter_by = request.args.get('filter')
    if filter_by:
        for task in tasks_list:
            if filter_by in task['name']:
                task['name_ru'] = tasks_trans(task['name'][len(filter_by) + 1:])
                result.append(task)
        return result

    # Все задачи
    tasks_names = []
    if not filter_by:

        for task in tasks_list:
            tasks_names.append(task['name'])

        # Группировка
        # Задачи API
        for api_name in API_NAMES:
            result.append({'group_name': api_name.capitalize()})
            n = len(tasks_list) - 1
            while n >= 0:
                task = tasks_list[n]
                if task['name'].startswith(api_name):
                    task['name_ru'] = tasks_trans(
                        task['name'][len(api_name)+1:]
                    )
                    result.append(task)
                    tasks_list.remove(task)
                n -= 1

        # Задачи вне API
        if len(tasks_list):
            result.append({'group_name': 'Остальные'})
            for task in tasks_list:
                task['name_ru'] = tasks_trans(task['name'])
                result.append(task)

        # Задачи из базы (удаленные)
        tasks_db = list(db.session.execute(
            db.select(Task)
            .filter(Task.name.notin_(tasks_names))).scalars())
        if len(tasks_db):
            result.append({'group_name': 'Не найдены'})
            for task in tasks_db:
                result.append({'deleted_name': task.name})

    return result


@bp.route('/tasks_action', methods=['GET'])
@admin_only
def tasks_action():
    action = request.args.get('action') or abort(404)
    task_id = request.args.get('task_id')
    task_name = request.args.get('task_name')
    filter_by = request.args.get('filter')

    tasks_list = get_tasks()
    active_ids = [task['id'] for task in tasks_list if task.get('id')]

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
            task_action(active_ids, action, task_id=task.get('id'),
                        task_name=task['name'])
            if action == 'start':
                time.sleep(0.1)
    return ''
