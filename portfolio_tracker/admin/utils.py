from __future__ import annotations
import json
import os
from functools import wraps
from datetime import datetime, timedelta, timezone
import time
from typing import Callable, Literal, TypeAlias
from io import BytesIO
import requests

from flask import current_app
from sqlalchemy import func
from PIL import Image


from ..app import db, redis, celery
from ..general_functions import Market, add_prefix, remove_prefix
from ..portfolio.models import Ticker
from ..watchlist.models import WatchlistAsset
from ..user.models import User


ApiName: TypeAlias = Literal['crypto', 'stocks', 'currency', 'proxy']
API_NAMES: tuple[ApiName, ...] = ('crypto', 'stocks', 'currency', 'proxy')

ApiLogCategory: TypeAlias = Literal['info', 'debug', 'warning', 'error']
ApiEvent: TypeAlias = Literal['not_updated_prices', 'new_tickers',
                              'not_found_tickers', 'updated_images']


class ApiLog:
    CATEGORIES: tuple[ApiLogCategory, ...] = ('info', 'debug', 'warning',
                                              'error')

    def key(self, api_name):
        return f"api.{api_name}.logs"

    def get(self, api_name: ApiName, timestamp: float) -> list:
        logs = []
        logs_key = self.key(api_name)
        for key in redis.hkeys(logs_key):
            key_timestamp = key.decode()
            if float(key_timestamp) > timestamp:
                log = redis.hget(logs_key, key).decode()
                log = json.loads(log)
                log['timestamp'] = key.decode()
                logs.append(log)

        return logs

    def set(self, category: ApiLogCategory, text: str, api_name: ApiName,
            task_name='') -> None:
        now = datetime.now(timezone.utc)
        timestamp = str(now.timestamp())
        text = f'{tasks_trans(task_name) + " - " if task_name else ""}{text}'
        log = {'text': text, 'category': self.CATEGORIES.index(category),
               'timestamp': timestamp, 'time': str(now)}
        redis.hset(self.key(api_name), timestamp, json.dumps(log))


class ApiInfo:
    def key(self, api_name):
        return f'api.{api_name}.info'

    def set(self, key: str, value, api_name: ApiName) -> None:
        redis.hset(self.key(api_name), key, str(value).encode('utf-8'))

    def get(self, key: str, api_name: ApiName) -> None:
        return redis.hget(self.key(api_name), key).decode()


class ApiData:
    def key(self, api_name):
        return f'api.{api_name}.data'

    def set(self, key: str, value: list | dict, api_name: ApiName) -> None:
        redis.hset(self.key(api_name), key, json.dumps(value))

    def get(self, key: str, api_name: ApiName, data_type):
        value = redis.hget(self.key(api_name), key)
        if value:
            value = json.loads(value.decode())

        return value if isinstance(value, data_type) else data_type()


class ApiEvents:
    EVENTS: dict[ApiEvent, str] = {'not_updated_prices': 'Не обновленые цены',
                                   'new_tickers': 'Новые тикеры',
                                   'not_found_tickers': 'Не найденные тикеры',
                                   'updated_images': 'Обновленные иконки'}

    def key(self, api_name):
        return f'api.{api_name}.events'

    def set(self, key: ApiEvent, value: list | dict, api_name: ApiName) -> None:
        redis.hset(self.key(api_name), key, json.dumps(value))

    def get(self, key: ApiEvent, api_name: ApiName, data_type=dict):
        value = redis.hget(self.key(api_name), key)
        if value:
            value = json.loads(value.decode())

        return value if isinstance(value, data_type) else data_type()

    def update(self, api_name: ApiName, ids_in_event: list[Ticker.id],
               event_name: ApiEvent, exclude_missing: bool = True) -> None:
        today_str = str(datetime.now().date())
        ids_in_db = api_event.get(event_name, api_name, dict)

        # Добавление ненайденных
        for ticker_id in ids_in_event:
            ids_in_db.setdefault(ticker_id, [])
            if today_str not in ids_in_db[ticker_id]:
                ids_in_db[ticker_id].append(today_str)

        # Исключение найденных
        if exclude_missing is True:
            for ticker_id in list(ids_in_db):
                if ticker_id not in ids_in_event:
                    del ids_in_db[ticker_id]
            api_event.set(event_name, ids_in_db, api_name)

    def delete(self, api_name, key):
        redis.hdel(self.key(api_name), key)


api_info = ApiInfo()
api_logging = ApiLog()
api_data = ApiData()
api_event = ApiEvents()


def get_tickers(market: Market | None = None,
                without_image: bool = False) -> list[Ticker]:
    select = db.select(Ticker).order_by(Ticker.market_cap_rank.is_(None),
                                        Ticker.market_cap_rank.asc())
    if market:
        select = select.filter_by(market=market)
    if without_image:
        select = select.filter_by(image=None)

    return list(db.session.execute(select).scalars())


def get_all_users() -> tuple[User, ...]:
    return tuple(db.session.execute(db.select(User)).scalars())


def get_tickers_count(market: Market) -> int:
    return db.session.execute(db.select(func.count()).select_from(Ticker)
                              .filter_by(market=market)).scalar() or 0


def get_users_count(user_type: str | None = None) -> int:
    select = db.select(func.count()).select_from(User)
    if user_type:
        select = select.filter_by(type=user_type)
    return db.session.execute(select).scalar() or 0


def find_ticker_in_base(external_id: str, tickers: list[Ticker],
                        market: Market) -> Ticker | None:
    ticker_id = add_prefix(external_id, market)

    for ticker in tickers:
        if ticker.id == ticker_id:
            return ticker


def create_new_ticker(external_id: str, market: Market) -> Ticker:
    ticker_id = add_prefix(external_id, market)

    ticker = Ticker()
    ticker.id = ticker_id
    ticker.market = market
    db.session.add(ticker)
    return ticker


def load_image(url: str, market: Market, ticker_id: Ticker.id,
               api_name: ApiName) -> str | None:

    # Папка хранения изображений
    upload_folder = current_app.config['UPLOAD_FOLDER']
    path = f'{upload_folder}/images/tickers/{market}'
    os.makedirs(path, exist_ok=True)

    ticker_id = remove_prefix(ticker_id, market)

    response = request_data(url, api_name)
    if not response:
        return

    try:
        original_img = Image.open(BytesIO(response.content))
        filename = f'{ticker_id}.{original_img.format}'.lower()
        api_logging.set('info', f'Загружена иконка ## {ticker_id}', market)
    except Exception as e:
        api_logging.set('error', f'Ошибка загрузки иконки: {type(e)}', market)
        current_app.logger.error('Ошибка', exc_info=True)
        raise

    def resize_image(px):
        size = (px, px)
        path_local = os.path.join(path, str(px))
        os.makedirs(path_local, exist_ok=True)
        path_saved = os.path.join(path_local, filename)
        original_img.resize(size).save(path_saved)

    resize_image(24)
    resize_image(40)

    return filename


def request_data(url: str, api_name: ApiName, stream: ApiStream | None = None
                 ) -> requests.models.Response | None:
    if not url.startswith('http'):
        return

    time.sleep(0.1)
    # Прокси
    proxies = {}
    if stream:
        stream.new_call()

        if stream.proxy:
            proxies = {'https': stream.proxy.replace('https', 'http'),
                       'http': stream.proxy.replace('https', 'http')}

    try:
        return requests.get(url, proxies=proxies)

    except requests.exceptions.ConnectionError as e:
        current_app.logger.warning(f'Ошибка: {e}', exc_info=True)
        api_logging.set('warning', f'Ошибка: {e}', api_name)

    except Exception as e:
        current_app.logger.error(f'Ошибка: {e}. url: {url}', exc_info=True)
        api_logging.set('error', f'Ошибка: {e}', api_name)
        raise


def response_json(response) -> dict:
    return response.json() if response else {}


def get_data(make_url: Callable, api: Api):
    while True:

        # Поиск потока
        stream = api.nearest_stream()
        if not stream:
            api_logging.set('warning', 'Нет потоков для запросов', api.name)
            return

        # Получение данных
        api_key = f'{api.key_prefix}{stream.key.api_key}' if stream.key else ''
        url = make_url(api_key)

        # Запрос
        response = request_data(url, api.name, stream)
        if response is None:
            continue

        # Обработка ответа
        if response.status_code == 200:
            pass

        elif response.status_code == 429:
            # Превышен лимит вызовов
            m = 'Превышен лимит запросов в минуту'
            current_app.logger.warning(m, exc_info=True)
            api_logging.set('warning', m, api.name)

            retry_after = int(response.headers.get('Retry-After', 120))
            retry_time = datetime.now() + timedelta(seconds=retry_after + 1)
            if retry_time > stream.next_call:
                stream.next_call = retry_time

            # Меняем лимиты
            if stream.update_minute_limit():
                api_logging.set('warning', 'Уменьшен лимит запросов в минуту', api.name)
            continue

        else:
            m = f'Ошибка, Код: {response.status_code}, {stream.name}, {url}'
            api_logging.set('error', m, api.name)
            current_app.logger.warning(m, exc_info=True)

        return response


def get_api(name) -> Api:
    from .models import Api
    api = db.session.execute(db.select(Api).filter_by(name=name)).scalar()
    if not api:
        api = Api(name=name)
        db.session.add(api)
    return api


def tasks_trans(name):
    # Api name
    name = name.replace('crypto', 'Крипто')
    name = name.replace('stocks', 'Акции')
    name = name.replace('currency', 'Валюта')
    name = name.replace('proxy', 'Прокси')
    name = name.replace('alerts', 'Уведомления')

    # Действие
    name = name.replace('load', 'загрузка')
    name = name.replace('update', 'обновление')

    # Объект
    name = name.replace('prices', 'цен')
    name = name.replace('tickers', 'тикеров')
    name = name.replace('images', 'картинок')
    name = name.replace('history', 'истории')

    # Пробелы
    name = name.replace('_', ' ')
    return name


def get_tasks() -> list:
    i = celery.control.inspect()
    active = i.active()
    scheduled = i.scheduled()
    registered = i.registered()

    tasks_list = []
    tasks_names = []
    if active:
        for server in active:
            for task in active[server]:
                tasks_list.append(
                    {'name': task['name'],
                     'name_ru': tasks_trans(task['name']),
                     'id': task['id']}
                )
                tasks_names.append(task['name'])

    if scheduled:
        for server in scheduled:
            for task in scheduled[server]:
                if task['request']['name'] not in tasks_names:
                    tasks_list.append(
                        {'name': task['request']['name'],
                         'name_ru': tasks_trans(task['request']['name']),
                         'id': task['request']['id']}
                    )
                    tasks_names.append(task['request']['name'])

    if registered:
        for server in registered:
            for task in registered[server]:
                if task not in tasks_names:
                    tasks_list.append(
                        {'name': task, 'name_ru': tasks_trans(task), 'id': ''}
                    )

    return tasks_list


def task_action(active_ids: list, action: str, task_id: str | None = None,
                task_name: str | None = None) -> None:
    if action == 'stop' and task_id in active_ids:
        celery.control.revoke(task_id, terminate=True)
    elif action == 'start' and task_id not in active_ids:
        task = celery.signature(task_name)
        task.delay()


def get_api_task(name):
    from .models import ApiTask
    return db.session.execute(db.select(ApiTask).filter_by(name=name)).scalar()


def get_api_key(key_id):
    from .models import ApiKey
    return db.session.execute(db.select(ApiKey).filter_by(id=key_id)).scalar()


def task_logging(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        start = time.perf_counter()
        func_name = func.__name__
        api_name = func_name[:func_name.find('_')]

        # Старт лог
        api_logging.set('info', 'Старт', api_name, func_name)
        current_app.logger.info(f'{func_name}: Старт')

        # task_func = func(*args, **kwargs)

        # Настройки следующего запуска
        next_run_time = None
        retry_after = None
        task = get_api_task(func_name)
        if task and task.retry_after():
            retry_after = task.retry_after()
            next_run_time = datetime.now() + timedelta(seconds=retry_after)
            next_run_time = next_run_time.isoformat(sep=' ', timespec='minutes')

        result = func(*args, retry_after=retry_after, **kwargs)

        # Конец лог
        wasted_time = smart_time(time.perf_counter() - start)
        mes = f'Конец #Time: {wasted_time}'
        mes2 = f'#Next: {next_run_time}' if next_run_time else ''

        current_app.logger.info(f'{func_name}: {mes}')
        api_logging.set('debug', f'{mes} {mes2}', api_name, func_name)

        return result

    return decorated_function


def smart_time(sec: float):
    m = int(sec // 60)
    s = sec - 60 * m if m else sec
    s = round(s % 60) if m else round(s % 60, 2)
    return (f'{m} мин.' if m else '') + (f'{s} сек.' if s else '')


def alerts_update(market):
    # Отслеживаемые тикеры
    tracked_tickers = db.session.execute(
        db.select(WatchlistAsset)
        .join(WatchlistAsset.ticker).filter_by(market=market)).scalars()

    for ticker in tracked_tickers:
        price = ticker.ticker.price
        # ToDo Перенести в запрос
        if not ticker.alerts or not price:
            continue

        for alert in ticker.alerts:
            if alert.status != 'on':
                continue

            if ((alert.type == 'down' and price <= alert.price)
                    or (alert.type == 'up' and price >= alert.price)):
                alert.status = 'worked'

    db.session.commit()
