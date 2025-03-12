from __future__ import annotations
import json
from functools import wraps
from datetime import datetime, timedelta, timezone
import time
from typing import TYPE_CHECKING, Dict, Literal, TypeAlias

from flask import current_app

from portfolio_tracker.app import db, redis
from portfolio_tracker.admin.models import Task

if TYPE_CHECKING:
    pass


class Integration:
    def __init__(self, module_name: str):
        self.name = module_name
        self.events = Event(module_name)
        self.info = Info(module_name)
        self.logs = Log(module_name)
        self.data = Data(module_name)


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
    def __init__(self, module_name: str) -> None:
        self.key = f'api.{module_name}.info'

    def set(self, key: str, value) -> None:
        redis.hset(self.key, key, str(value).encode('utf-8'))

    def get(self, key: str) -> None:
        return redis.hget(self.key, key).decode()


class Data:
    def __init__(self, module_name: str) -> None:
        self.key = f'api.{module_name}.data'

    def set(self, key: str, value: list | dict) -> None:
        redis.hset(self.key, key, json.dumps(value))

    def get(self, key: str, data_type: type) -> dict:
        value = redis.hget(self.key, key)
        if value:
            value = json.loads(value.decode())

        return value if isinstance(value, data_type) else data_type()


class Event:
    def __init__(self, module_name: str) -> None:
        self.key = f'api.{module_name}.events'

    def set(self, key: str, value: list | dict) -> None:
        redis.hset(self.key, key, json.dumps(value))

    def get(self, key: str, data_type=dict):
        value = redis.hget(self.key, key)
        if value:
            value = json.loads(value.decode())

        return value if isinstance(value, data_type) else data_type()

    def delete(self, key):
        redis.hdel(self.key, key)


def task_logging(function):
    @wraps(function)
    def decorated_function(task):
        from .utils import get_module
        from .integrations_api import ApiIntegration

        module_name = task.name[:task.name.find('_')]

        module = get_module(module_name)
        if not module:
            print('Модуль не найден')
            return

        # Блокировка модуля
        if isinstance(module, ApiIntegration):
            # Ожидание завершения уже запущенной задачи
            while module.is_working_now():
                time.sleep(60)

            # Блокировка других задач модуля
            module.start_work()

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
        if task_settings and task_settings.retry_after:
            retry_after = task_settings.retry_after
            task.default_retry_delay = retry_after
            run_time = datetime.now() + timedelta(seconds=retry_after)
            next_run_time = run_time.isoformat(sep=' ', timespec='minutes')

        # Конец лог
        wasted_time = smart_time(time.perf_counter() - start)
        mes = f'Конец #Time: {wasted_time}'
        mes2 = f'#Next: {next_run_time}' if next_run_time else ''
        module.logs.set('debug', f'{mes} {mes2}', task.name)
        current_app.logger.info(f'{task.name}: {mes}')

        # Разблокировка модуля
        if isinstance(module, ApiIntegration):
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
