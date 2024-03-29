import re
import time
from flask import abort, flash, redirect, render_template, url_for, request

from ..app import db, redis
from ..wraps import admin_only
from ..jinja_filters import user_datetime
from ..general_functions import MARKETS, actions_in, when_updated
from ..portfolio.utils import get_ticker
from ..user.utils import find_user
from ..user.models import User
from .models import Key, Task
from .integrations import Log, get_api_task, tasks_trans
from .integrations_api import API_NAMES, ApiIntegration
from .integrations_other import MODULE_NAMES
from .utils import get_all_users, get_key, get_module, get_stream, get_tasks, \
    get_tickers, get_tickers_count, task_action
from . import bp


@bp.route('/updater', methods=['GET'])
@admin_only
def updater():
    # Обновление средней цены актива
    try:
        pass
        # for user in db.session.execute(db.select(User)).scalars():
        #     for portfolio in user.portfolios:
        #         for asset in portfolio.assets:
        #             # Если обновлено - пропускаем
        #             # if asset.average_buy_price:
        #             #     continue
        #
        #             if asset.quantity:
        #                 asset.average_buy_price = asset.amount / asset.quantity
        #             else:
        #                 asset.average_buy_price = 0
        #
        # db.session.commit()
        flash('Обновления вополнены', 'success')
    except Exception as e:
        flash(f'Ошибка. {e}', 'warning')
    return redirect(url_for('.module_page'))


@bp.route('/index', methods=['GET'])
@admin_only
def index():
    return redirect(url_for('.module_page'))


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
    actions_in(request.data, find_user)
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


@bp.route('/demo_page', methods=['GET'])
@admin_only
def demo_page():
    return render_template('admin/demo_page.html')


@bp.route('/demo/action', methods=['GET'])
@admin_only
def demo_action():
    action = request.args.get('action')
    if action == 'allow':
        flash('С этого IP изменения разрешены', 'success')
    elif action == 'disallow':
        flash('Изменения запрещены', 'warning')
    return redirect(url_for('.demo_page'))


@bp.route('/module', methods=['GET', 'POST'])
@admin_only
def module_page():
    module = get_module(request.args.get('module_name'))

    return render_template('admin/module_page.html', module=module,
                           log_categories=Log.CATEGORIES,
                           module_names=API_NAMES + MODULE_NAMES)


@bp.route('/module/detail', methods=['GET'])
@admin_only
def module_page_detail():
    module_name = request.args.get('module_name')
    result = {'info': [], 'streams': [], 'events': []}

    # Для итерации по модулям
    module_list = [module_name] if module_name else API_NAMES + MODULE_NAMES
    for name in module_list:
        module = get_module(name)
        if not module:
            continue

        # События
        events_list = []
        for event_name in redis.hkeys(module.events.key):
            count = len(module.events.get(event_name))
            event_name = event_name.decode()
            events_list.append({'name': module.events.list.get(event_name),
                                'key': event_name, 'value': f'{count}'})

        # Заголовок в событиях
        if len(module_list) > 1 and events_list:
            result['events'].append({'group_name': module.name.capitalize()})
        result['events'] += events_list

        info_list = []

        # Тикеры
        if name in MARKETS:
            info_list.append({'name': 'Количество тикеров',
                              'value': get_tickers_count(module.api.name)})

        # Информация
        for info_name in redis.hkeys(module.info.key):
            value = module.info.get(info_name)

            # Если дата
            if re.search(r'\d{4}-\d{2}-\d{2}', value):
                value = when_updated(value)

            info_list.append({'name': f'{info_name.decode()}', 'value': value})

        # Заголовок в информации
        if len(module_list) > 1 and info_list:
            result['info'].append({'group_name': name.capitalize()})
        result['info'] += info_list

        # Потоки
        if len(module_list) > 1 or not isinstance(module, ApiIntegration):
            continue
        for stream in module.api.streams:
            result['streams'].append(
                {'name': stream.name, 'class': 'text-average',
                 'id': stream.id,
                 'calls': f'{stream.month_calls} из {module.api.month_limit or "∞"}',
                 'api_key': f'*{stream.key.api_key[-10:]}' if stream.key else 'без ключа',
                 'called': when_updated(stream.next_call, 'Никогда'),
                 'status': 'Активный' if stream.active else 'Не активный'}
            )

    return result


@bp.route('/module/logs', methods=['GET'])
@admin_only
def json_module_logs():
    timestamp = request.args.get('timestamp', 0.0, type=float)
    module_name = request.args.get('module_name')
    logs = []

    # Для итерации по модулям
    module_list = [module_name] if module_name else API_NAMES + MODULE_NAMES
    for module in module_list:
        module_logs = Log(module)
        logs += module_logs.get(timestamp)

    if logs:
        logs = sorted(logs, key=lambda log: log.get('timestamp'))
    return logs


@bp.route('/module/logs_delete', methods=['POST'])
@admin_only
def module_logs_delete():
    module_name = request.args.get('module_name')

    # Для итерации по модулям
    module_list = [module_name] if module_name else API_NAMES + MODULE_NAMES
    for name in module_list:
        module = get_module(name)
        if not module:
            continue

        redis.delete(module.logs.key)

    return redirect(url_for('.module_page', module_name=module_name))


@bp.route('/module/events', methods=['GET'])
@admin_only
def module_event_info():
    event = request.args.get('event')

    module = get_module(request.args.get('module_name')) or abort(404)
    data = module.evets_info(event) if hasattr(module, 'evets_info') else {}

    return render_template('admin/api_event.html', data=data,
                           event=event, module=module)


@bp.route('/api/key_settings/', methods=['GET', 'POST'])
@admin_only
def api_key_settings():
    module = ApiIntegration(request.args.get('api_name'))
    api = module.api

    key = get_key(request.args.get('key_id')) or Key(api_id=api.id)

    if request.method == 'POST':
        key.edit(request.form)
        # Обновляем потоки
        module.update_streams()
        return ''

    return render_template('admin/api_key_settings.html', key=key, api=api)


@bp.route('/api/key_action/', methods=['POST'])
@admin_only
def api_key_action():
    actions_in(request.data, get_key)

    module = ApiIntegration(request.args.get('api_name'))
    module.update_streams()
    return ''


@bp.route('/api/stream_settings/', methods=['GET', 'POST'])
@admin_only
def api_stream_settings():
    stream = get_stream(request.args.get('stream_id')) or abort(404)

    if request.method == 'POST':
        stream.edit(request.form)
        return ''

    return render_template('admin/api_stream_settings.html', stream=stream)


@bp.route('/api/stream_action/', methods=['POST'])
@admin_only
def api_stream_action():
    actions_in(request.data, get_stream)
    return ''


@bp.route('/api/events', methods=['POST'])
@admin_only
def api_event_action():
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

    return render_template('admin/api_task_settings.html', task_name=task_name,
                           task_ru_name=tasks_trans(task_name), task=task)


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
        # Задачи модулей
        for module in API_NAMES + MODULE_NAMES:
            n = len(tasks_list) - 1
            module_tasks = []
            while n >= 0:
                task = tasks_list[n]
                if task['name'].startswith(module):
                    task['name_ru'] = tasks_trans(
                        task['name'][len(module)+1:]
                    )
                    module_tasks.append(task)
                    tasks_list.remove(task)
                n -= 1

            if module_tasks:
                result.append({'group_name': module.capitalize()})
                result += module_tasks

        # Задачи вне модулей
        if tasks_list:
            result.append({'group_name': 'Остальные'})
            for task in tasks_list:
                task['name_ru'] = tasks_trans(task['name'])
                result.append(task)

        # Задачи из базы (удаленные)
        tasks_db = list(db.session.execute(
            db.select(Task).filter(Task.name.notin_(tasks_names))).scalars())
        if tasks_db:
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
