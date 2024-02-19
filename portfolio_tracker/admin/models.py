from __future__ import annotations
from datetime import datetime, timedelta
import time
from typing import List

from sqlalchemy.orm import Mapped
from werkzeug.datastructures.structures import ImmutableMultiDict

from ..app import db, redis
from .utils import ApiName
from . import proxy


class Api(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name: ApiName = db.Column(db.String(32))
    need_key: bool = db.Column(db.Boolean)
    need_proxy: bool = db.Column(db.Boolean, default=True)
    minute_limit: int = db.Column(db.Integer, default=0)
    month_limit: int = db.Column(db.Integer, default=0)
    key_prefix: str = db.Column(db.String(32), default='')
    lock_time: datetime = db.Column(db.DateTime)
    streams_lock: bool = db.Column(db.Boolean, default=True)

    # Relationships
    keys: Mapped[List[ApiKey]] = db.relationship(
        'ApiKey', backref=db.backref('api', lazy=True))
    streams: Mapped[List[ApiStream]] = db.relationship(
        'ApiStream', backref=db.backref('api', lazy=True))

    def edit(self, form: ImmutableMultiDict) -> None:
        self.minute_limit = form.get('minute_limit', 0, type=int)
        self.month_limit = form.get('month_limit', 0, type=int)
        self.key_prefix = form.get('key_prefix', '', type=str)

        need_key = form.get('need_key', False, type=bool)
        if self.need_key != need_key:
            self.need_key = need_key
            self.update_streams()

        need_proxy = form.get('need_proxy', False, type=bool)
        if self.need_proxy != need_proxy:
            self.need_proxy = need_proxy
            self.update_streams()

        db.session.commit()

    def update_streams(self) -> None:

        # Использование без прокси
        if self.need_proxy is False:
            if not self.streams:
                self.streams.append(
                    ApiStream(name=f'Поток {len(self.streams) + 1}'))
            self.streams[0].api_key_id = self.keys[0].id if self.keys else None
            db.session.commit()
            return

        proxies = proxy.get_proxies()

        # Список свободных ключей
        free_keys = [key.id for key in self.keys if not key.stream]

        for stream in self.streams:
            # Сопоставляем свободные ключи
            if self.need_key and not stream.key:
                stream.api_key_id = free_keys.pop() if free_keys else None
            # Обновляем статус потока и убираем занятые прокси
            has_proxy = bool(proxies.pop(stream.proxy_id, False))
            has_key_if_need = bool(not self.need_key or stream.key)
            stream.active = has_proxy and has_key_if_need

        # Если есть свободные прокси - добавляем потоки
        while len(proxies) > 0 and (not self.need_key or len(free_keys) > 0):
            p = proxies.pop(list(proxies.keys())[0])
            new_stream = ApiStream(
                name=f'Поток {len(self.streams) + 1}',
                api_key_id=free_keys.pop() if free_keys else None,
                proxy_id=p['id'],
                proxy=f"{p['type']}://{p['user']}:{p['pass']}@{p['host']}:{p['port']}")
            self.streams.append(new_stream)

        db.session.commit()

    def streams_are_blocked(self) -> bool:
        lock_timestamp = redis.get(f'api.{self.name}.streams_blocked')
        if lock_timestamp:
            timestamp_now = datetime.now().timestamp()
            return float(lock_timestamp.decode()) + 5 > float(timestamp_now)
        return False

    def block_streams(self) -> None:
        redis.set(f'api.{self.name}.streams_blocked',
                  str(datetime.now().timestamp()))

    def unblock_streams(self) -> None:
        redis.delete(f'api.{self.name}.streams_blocked')

    def nearest_stream(self) -> ApiStream | None:
        while self.streams_are_blocked():
            time.sleep(0.1)

        self.block_streams()

        # Поиск ближайшего потока
        result = None
        for stream in self.streams:
            # Отсеиваем неактивные
            if stream.active is False:
                continue

            # Сразу отдаем, если еще не использовался
            if not stream.next_call:
                result = stream
                break

            # Ищем ближайший поток
            if result is None or stream.next_call < result.next_call:
                result = stream

        if not result:
            self.unblock_streams()

        return result


class ApiKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    api_id: Api.id = db.Column(db.Integer, db.ForeignKey('api.id'))
    api_key: str = db.Column(db.String(1024))
    comment: str = db.Column(db.Text)

    def edit(self, form: ImmutableMultiDict) -> None:
        if not self.id:
            db.session.add(self)
        self.api_key = form['api_key']
        self.comment = form['comment']
        db.session.commit()
        # Обновляем потоки
        self.api.update_streams()


class ApiStream(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    api_id: Api.id = db.Column(db.Integer, db.ForeignKey('api.id'))
    api_key_id: ApiKey.id = db.Column(db.Integer, db.ForeignKey('api_key.id'))
    proxy_id: str = db.Column(db.String(128))
    proxy: str = db.Column(db.String(256))
    month_calls: int = db.Column(db.Integer, default=0)
    minute_calls: int = db.Column(db.Integer, default=0)
    first_call_minute: datetime = db.Column(db.DateTime)
    first_call_month: datetime = db.Column(db.DateTime)
    next_call: datetime = db.Column(db.DateTime)
    active: bool = db.Column(db.Boolean, default=True)
    busy: bool = db.Column(db.Boolean, default=False)

    # Relationships
    key: Mapped[List[ApiKey]] = db.relationship(
        'ApiKey', backref=db.backref('stream', uselist=False, lazy=True))

    def new_call(self) -> None:
        now = datetime.now()
        # db.session.refresh(self)
        db.session.commit()  # Для обновления данных (параллель)
        next_call = self.next_call
        delay = 0
        if next_call:
            delay = (next_call - now).total_seconds()
            delay = delay if delay > 0 else 0

        # Если после запуска будет больше минуты с первого запроса - обнуляем
        if (not self.first_call_minute or
                now + timedelta(seconds=delay) > self.first_call_minute + timedelta(seconds=60)):
            self.first_call_minute = now + timedelta(seconds=delay)
            self.minute_calls = 0

        # Прошло более месяца с первого запроса - обнуляем
        if (not self.first_call_month or
                now > self.first_call_month + timedelta(days=31)):
            self.first_call_month = now + timedelta(seconds=delay)
            self.month_calls = 0

        # Счетчики
        self.minute_calls += 1
        self.month_calls += 1

        # Следующий вызов
        # Записываем следующий вызов в зависимости от лимита в минуту
        if self.api.minute_limit and self.minute_calls >= self.api.minute_limit:
            self.next_call = self.first_call_minute + timedelta(seconds=60 + delay)

        # Перезаписываем следующий вызов в зависимости от лимита в месяц
        if self.api.month_limit and self.month_calls >= self.api.month_limit:
            self.next_call = self.first_call_month + timedelta(days=31)

        db.session.commit()
        # db.session.expire(self)
        self.api.unblock_streams()

        # Задержка до запроса (если есть)
        time.sleep(delay)

    def update_minute_limit(self) -> bool:
        # Если нет минутного лимита - задаем
        if not self.api.minute_limit:
            self.api.minute_limit = self.minute_calls
        # Уменьшаем лимит
        if self.api.minute_limit > 1:
            self.api.minute_limit -= 1
            db.session.commit()
            return True  # Обновлено
        return False  # Не обновлено


class ApiTask(db.Model):
    name = db.Column(db.String(128), primary_key=True)
    api_name: ApiName = db.Column(db.String(32))
    retry_period_type: int = db.Column(db.Integer, default=0)
    retry_period_count: int = db.Column(db.Integer, default=0)

    def edit(self, form: ImmutableMultiDict, api_name: ApiName) -> None:
        self.api_name = api_name
        self.retry_period_type = form.get('retry_period_type', 0, type=int)
        self.retry_period_count = form.get('retry_period_count', 0, type=int)
        db.session.commit()

    def retry_after(self) -> int:
        return 60 * self.retry_period_type * self.retry_period_count  # секунды
