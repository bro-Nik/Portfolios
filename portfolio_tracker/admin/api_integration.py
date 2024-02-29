from __future__ import annotations
import json
from functools import wraps
from datetime import datetime, timedelta, timezone
import time
from typing import TYPE_CHECKING, Callable, Dict, Literal, TypeAlias
import requests

from flask import current_app

from ..app import db, redis
from ..portfolio.models import Ticker
from .models import Api, Stream, Task

if TYPE_CHECKING:
    pass


ApiName: TypeAlias = Literal['crypto', 'stocks', 'currency', 'proxy']
API_NAMES: tuple[ApiName, ...] = ('crypto', 'stocks', 'currency', 'proxy')


class ApiIntegration:
    def __init__(self, name: str | None):
        if name not in API_NAMES:
            return

        api = db.session.execute(db.select(Api).filter_by(name=name)).scalar()
        if not api:
            api = Api(name=name)
            db.session.add(api)
        self.api = api
        # if api.id:
        #     self.update_streams()

        self.events = Event(name)
        self.info = Info(name)
        self.logs = Log(name)
        self.data = Data(name)

    def update_streams(self) -> None:
        from . import proxy
        api = self.api

        # Использование без прокси
        if api.need_proxy is False:
            if not api.streams:
                api.streams.append(
                    Stream(name=f'Поток {len(api.streams) + 1}'))
            api.streams[0].api_key_id = api.keys[0].id if api.keys else None
            db.session.commit()
            return

        proxies = proxy.get_proxies()

        # Список свободных ключей
        free_keys = [key.id for key in api.keys if not key.stream]

        for stream in api.streams:
            # Сопоставляем свободные ключи
            if api.need_key and not stream.key:
                stream.api_key_id = free_keys.pop() if free_keys else None
            # Обновляем статус потока и убираем занятые прокси
            has_proxy = bool(proxies.pop(stream.proxy_id, False))
            has_key_if_need = bool(not api.need_key or stream.key)
            stream.active = has_proxy and has_key_if_need

        # Если есть свободные прокси - добавляем потоки
        while len(proxies) > 0 and (not api.need_key or len(free_keys) > 0):
            p = proxies.pop(list(proxies.keys())[0])
            new_stream = Stream(
                name=f'Поток {len(api.streams) + 1}',
                api_key_id=free_keys.pop() if free_keys else None,
                proxy_id=p['id'],
                proxy=f"{p['type']}://{p['user']}:{p['pass']}@{p['host']}:{p['port']}")
            api.streams.append(new_stream)

        db.session.commit()

    def start_work(self) -> None:
        redis.set(f'api.{self.api.name}.working', str(datetime.now()))

    def is_working_now(self) -> bool:
        time_start = redis.get(f'api.{self.api.name}.working')
        if not time_start:
            return False

        time_start = datetime.strptime(time_start.decode(),
                                       '%Y-%m-%d %H:%M:%S.%f')
        return datetime.now() < time_start + timedelta(hours=2)

    def end_work(self) -> None:
        redis.delete(f'api.{self.api.name}.working')

    def nearest_stream(self) -> Stream | None:
        """ Поиск ближайшего потока """
        max_time = datetime.now() + timedelta(minutes=10)
        stmt = (db.select(Stream)
                .filter(Stream.api_id == self.api.id,
                        Stream.active,
                        Stream.next_call < max_time)
                .order_by(Stream.next_call.asc()))
        return db.session.execute(stmt).scalar()

    def new_call(self, stream) -> None:
        api = self.api
        now = datetime.now()
        next_call = stream.next_call
        delay = 0
        if next_call:
            delay = (next_call - now).total_seconds()
            delay = delay if delay > 0 else 0

        # Время запуска после задержки
        run_time = now + timedelta(seconds=delay)

        # Если после запуска будет больше минуты с первого запроса - обнуляем
        if run_time > stream.first_call_minute + timedelta(seconds=60):
            stream.first_call_minute = run_time
            stream.minute_calls = 0

        # Настал следующий месяц после первого запроса - обнуляем
        if (run_time.month > stream.first_call_month.month
                or run_time.year > stream.first_call_month.year):
            stream.first_call_month = run_time
            stream.month_calls = 0

        # Счетчики
        stream.minute_calls += 1
        stream.month_calls += 1

        # Записываем следующий вызов в зависимости от лимита в минуту
        if api.minute_limit and stream.minute_calls >= api.minute_limit:
            next_call = stream.first_call_minute + timedelta(seconds=60 + delay)
            self.change_next_call(next_call, stream)

        # Перезаписываем следующий вызов в зависимости от лимита в месяц
        if api.month_limit and stream.month_calls >= api.month_limit:
            self.next_month_call(stream)

        db.session.commit()
        # stream.api.unblock_streams()

        print(
            f'Поток: {stream.id}, next_call: {stream.next_call},'
            f'calls: {stream.minute_calls}, delay: {delay}')

        # Задержка до запроса (если есть)
        time.sleep(delay)

    def update_minute_limit(self, retry_after, stream) -> None:
        # Если нет минутного лимита - задаем
        if not self.api.minute_limit:
            self.api.minute_limit = stream.minute_calls

        self.change_next_call(datetime.now() + timedelta(seconds=retry_after),
                              stream)

        # Уменьшаем лимит
        if self.api.minute_limit > 1:
            self.api.minute_limit -= 1
            # Лог
            self.logs.set('warning',
                          f'Уменьшен лимит запросов в минуту. {stream.name}')
        db.session.commit()

    def change_next_call(self, next_datetime, stream):
        stream.next_call = max(stream.next_call, next_datetime)

    def next_month_call(self, stream):
        # Следующий вызов 1 числа следующего месяца
        now = datetime.now()
        month = now.month + 1 if now.month != 12 else 1
        year = now.year + 1 if month == 1 else now.year
        next_month_call = datetime(year=year, month=month, day=1, hour=12)
        self.change_next_call(next_month_call, stream)
        db.session.commit()

    def request(self, make_url: Callable) -> requests.models.Response | None:
        api = self.api
        while True:
            # Поиск потока
            stream = self.nearest_stream()
            if not stream:
                self.logs.set('warning', 'Нет потоков для запросов')
                return

            # Получение данных
            key = f'{api.key_prefix}{stream.key.api_key}' if stream.key else ''
            url = make_url(key)

            # Запрос
            response = request_data(self, url, stream)

            # Проверка на превышение минутного лимита
            if hasattr(self, 'minute_limit_trigger'):
                retry_after = self.minute_limit_trigger(response)
                if retry_after:
                    # Логи
                    m = f'Превышен лимит запросов в минуту. {stream.name}'
                    current_app.logger.warning(m, exc_info=True)
                    self.logs.set('warning', m)

                    # Уменьшить лимит
                    self.update_minute_limit(retry_after, stream)
                    continue

            # Проверка на превышение месячного лимита
            if hasattr(self, 'monthly_limit_trigger'):
                # Превышен лимит запросов в месяц
                if self.monthly_limit_trigger(response):
                    # Логи
                    m = f'Превышен лимит запросов в месяц. {stream.name}'
                    current_app.logger.warning(m, exc_info=True)
                    self.logs.set('warning', m)

                    # Отодвинуть следующий вызов
                    self.next_month_call(stream)
                    continue

            return response


def request_data(api, url: str, stream: Stream | None = None
                 ) -> requests.models.Response | None:
    if not url.startswith('http'):
        return

    # time.sleep(0.1)
    # Прокси
    proxies = {}
    if stream:
        api.new_call(stream)

        if stream.proxy:
            proxies = {'https': stream.proxy.replace('https', 'http'),
                       'http': stream.proxy.replace('https', 'http')}

    try:
        return requests.get(url, proxies=proxies)

    except requests.exceptions.ConnectionError as e:
        current_app.logger.error(f'Ошибка: {e}', exc_info=True)
        api.logs.set('error', f'Ошибка: {e}')

    except Exception as e:
        current_app.logger.error(f'Ошибка: {e}. url: {url}', exc_info=True)
        api.logs.set('error', f'Ошибка: {e}')
        raise


class Log:
    Category: TypeAlias = Literal['info', 'debug', 'warning', 'error']
    CATEGORIES: tuple[Category, ...] = ('info', 'debug', 'warning', 'error')

    def __init__(self, name: ApiName) -> None:
        self.key = f'api.{name}.logs'

    def get(self, timestamp: float = 0.0) -> list:
        logs = []
        for key in redis.hkeys(self.key):
            key_timestamp = key.decode()
            if float(key_timestamp) > timestamp:
                log = redis.hget(self.key, key).decode()
                log = json.loads(log)
                log['timestamp'] = key.decode()
                logs.append(log)

        return logs

    def set(self, category: Category, text: str, task_name='') -> None:
        now = datetime.now(timezone.utc)
        timestamp = str(now.timestamp())
        text = f'{tasks_trans(task_name) + " - " if task_name else ""}{text}'
        log = {'text': text, 'category': self.CATEGORIES.index(category),
               'timestamp': timestamp, 'time': str(now)}
        redis.hset(self.key, timestamp, json.dumps(log))

    @classmethod
    def clear(cls, settings: Dict[Category, int]) -> None:
        """ Очистка логов """
        # Сколько дней хранить по категории
        # settings: dict[Category, int] = {'info': 7, 'debug': 0, 'warning': 60}

        now = datetime.now()
        timestamp = []
        for category in cls.CATEGORIES:
            days = settings.get(category)
            timestamp.append((now - timedelta(days=days)).timestamp()
                             if days is not None else 0)

        for api_name in API_NAMES:
            for key in redis.hkeys(f'api.{api_name}.logs'):
                key_timestamp = key.decode()
                log = redis.hget(f'api.{api_name}.logs', key).decode()
                log = json.loads(log)

                if float(key_timestamp) <= timestamp[log['category']]:
                    redis.hdel(f'api.{api_name}.logs', key)


class Info:
    def __init__(self, api_name: ApiName) -> None:
        self.key = f'api.{api_name}.info'

    def set(self, key: str, value) -> None:
        redis.hset(self.key, key, str(value).encode('utf-8'))

    def get(self, key: str) -> None:
        return redis.hget(self.key, key).decode()


class Data:
    def __init__(self, api_name: ApiName) -> None:
        self.key = f'api.{api_name}.data'

    def set(self, key: str, value: list | dict) -> None:
        redis.hset(self.key, key, json.dumps(value))

    def get(self, key: str, data_type: type):
        value = redis.hget(self.key, key)
        if value:
            value = json.loads(value.decode())

        return value if isinstance(value, data_type) else data_type()


class Event:
    Events: TypeAlias = Literal['not_updated_prices', 'new_tickers',
                                'not_found_tickers', 'updated_images']
    EVENTS: dict[Events, str] = {'not_updated_prices': 'Цены не обновлены',
                                 'new_tickers': 'Новые тикеры',
                                 'not_found_tickers': 'Тикеры не найдены',
                                 'updated_images': 'Обновлены картинки'}

    def __init__(self, api_name: ApiName) -> None:
        self.key = f'api.{api_name}.events'

    def set(self, key: Events, value: list | dict) -> None:
        redis.hset(self.key, key, json.dumps(value))

    def get(self, key: Events, data_type=dict):
        value = redis.hget(self.key, key)
        if value:
            value = json.loads(value.decode())

        return value if isinstance(value, data_type) else data_type()

    def update(self, ids_in_event: list[Ticker.id],
               event_name: Events, exclude_missing: bool = True) -> None:
        today_str = str(datetime.now().date())
        ids_in_db = self.get(event_name, dict)

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
            self.set(event_name, ids_in_db)

    def delete(self, key):
        redis.hdel(self.key, key)


def task_logging(function):
    @wraps(function)
    def decorated_function(task):
        api_name = task.name[:task.name.find('_')]
        api = ApiIntegration(api_name)
        while api.is_working_now():
            print(f'{task.name}: Ожидаем')
            time.sleep(60)

        api.start_work()
        start = time.perf_counter()

        # Старт лог
        api.logs.set('info', 'Старт', task.name)
        current_app.logger.info(f'{task.name}: Старт')

        try:
            result = function(task)
        except Exception as e:
            api.logs.set('error', f'Ошибка: {e}', task.name)
            return

        # Настройки следующего запуска
        next_run_time = None
        retry_after = None
        task_settings = get_api_task(task.name)
        if task_settings and task_settings.retry_after():
            retry_after = task_settings.retry_after()
            task.default_retry_delay = retry_after
            next_run_time = datetime.now() + timedelta(seconds=retry_after)
            next_run_time = next_run_time.isoformat(sep=' ', timespec='minutes')

        # Конец лог
        wasted_time = smart_time(time.perf_counter() - start)
        mes = f'Конец #Time: {wasted_time}'
        mes2 = f'#Next: {next_run_time}' if next_run_time else ''

        current_app.logger.info(f'{task.name}: {mes}')
        api.logs.set('debug', f'{mes} {mes2}', task.name)

        api.end_work()

        # Следующий запуск
        if retry_after:
            task.retry()

        return result

    return decorated_function


def smart_time(sec: float):
    m = int(sec // 60)
    s = sec - 60 * m if m else sec
    s = round(s % 60) if m else round(s % 60, 2)
    return (f'{m} мин.' if m else '') + (f'{s} сек.' if s else '')


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
    return name.capitalize()


def get_api_task(name):
    return db.session.execute(db.select(Task).filter_by(name=name)).scalar()
