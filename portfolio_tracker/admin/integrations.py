from __future__ import annotations
import json
from functools import wraps
from datetime import datetime, timedelta, timezone
import time
from typing import TYPE_CHECKING, Dict, Literal, TypeAlias

from flask import current_app

from ..app import db, redis
from .models import Task
from .integrations_api import API_NAMES, ApiIntegration
from .integrations_module import MODULE_NAMES, ModuleIntegration

if TYPE_CHECKING:
    from ..portfolio.models import Ticker


class Log:
    Category: TypeAlias = Literal['info', 'debug', 'warning', 'error']
    CATEGORIES: tuple[Category, ...] = ('info', 'debug', 'warning', 'error')

    def __init__(self, module_name: str) -> None:
        self.key = f'api.{module_name}.logs'

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

        for log_key in redis.keys('api.*.logs'):
            log_key = log_key.decode()
            for log_item in redis.hkeys(log_key):
                key_timestamp = log_item.decode()
                log = redis.hget(log_key, log_item).decode()
                log = json.loads(log)

                if float(key_timestamp) <= timestamp[log['category']]:
                    redis.hdel(log_key, log_item)


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
        module_name = task.name[:task.name.find('_')]
        print(module_name)

        module = None
        if module_name in API_NAMES:
            module = ApiIntegration(module_name)
            while module.is_working_now():
                time.sleep(60)

            module.start_work()

        if module_name in MODULE_NAMES:
            module = ModuleIntegration(module_name)
            print(module_name)
            print(module)

        if not module:
            print('Модуль не найден')
            return

        start = time.perf_counter()

        # Старт лог
        module.logs.set('info', 'Старт', task.name)
        current_app.logger.info(f'{task.name}: Старт')

        try:
            result = function(task)
        except Exception as e:
            module.logs.set('error', f'Ошибка: {e}', task.name)
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
        module.logs.set('debug', f'{mes} {mes2}', task.name)

        if hasattr(module, 'end_work'):
            module.end_work()

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

    # Другое
    name = name.replace('other', 'Другие задачи')
    name = name.replace('logging', 'логи')
    name = name.replace('clear', 'очистка')

    # Пробелы
    name = name.replace('_', ' ')
    return name.capitalize()


def get_api_task(name):
    return db.session.execute(db.select(Task).filter_by(name=name)).scalar()
