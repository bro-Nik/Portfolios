from __future__ import annotations
from datetime import datetime, timedelta
import time
from typing import TYPE_CHECKING, Callable, Literal, TypeAlias
import requests

from flask import current_app

from portfolio_tracker.admin.repository import ApiRepository
from portfolio_tracker.app import db, redis
from portfolio_tracker.admin.models import Stream
from portfolio_tracker.admin.services import integrations

if TYPE_CHECKING:
    pass


ApiName: TypeAlias = Literal['crypto', 'stocks', 'currency', 'proxy']
API_NAMES: tuple[ApiName, ...] = ('crypto', 'stocks', 'currency', 'proxy')


class ApiIntegration(integrations.Integration):
    def __init__(self, name: str | None):
        if name in API_NAMES:
            super().__init__(name)
            self.api = ApiRepository.get_by_name(name) or ApiRepository.create(name=name)

    def minute_limit_trigger(self, response: requests.models.Response) -> int | bool:
        return False

    def monthly_limit_trigger(self, response: requests.models.Response) -> bool:
        return False

    def update_streams(self) -> None:
        from portfolio_tracker.admin import proxy
        api = self.api

        # Использование без прокси
        if api.need_proxy is False:
            if not api.streams:
                api.streams.append(Stream(name=f'Поток {len(api.streams) + 1}'))
            api.streams[0].api_key_id = api.keys[0].id if api.keys else None
            db.session.commit()
            return

        proxies = proxy.get_proxies()

        # Список свободных ключей
        free_keys = [key.id for key in api.keys if not key.stream]

        streams_without_proxy = []
        for stream in api.streams:

            # Сопоставляем свободные ключи
            if api.need_key and not stream.key:
                stream.api_key_id = free_keys.pop() if free_keys else None
            stream.active = bool(not api.need_key or stream.api_key_id)

            # Проверяем актуальность прокси и убираем занятые прокси
            if not bool(proxies.pop(stream.proxy_id, False)) and stream.active:
                streams_without_proxy.append(stream)

        # Если есть свободные прокси
        while proxies:
            p = proxies.pop(list(proxies.keys())[0])
            stream = None

            # Существующий поток с устаревшим прокси
            if streams_without_proxy:
                stream = streams_without_proxy.pop()

            # Добавляем поток
            if not stream and not api.need_key or free_keys:
                stream = Stream(
                    name=f'Поток {len(api.streams) + 1}',
                    api_key_id=free_keys.pop() if free_keys else None
                )
                api.streams.append(stream)

            # Обновляем проки у потока
            if stream:
                stream.proxy_id = p['id']
                stream.proxy = (f"{p['type']}://{p['user']}:{p['pass']}@"
                                f"{p['host']}:{p['port']}")
            else:
                break

        # Отключаем потоки без прокси
        for stream in streams_without_proxy:
            stream.active = False

        ApiRepository.save(self.api)

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
        delay = (next_call - now).total_seconds()
        delay = delay if delay > 0 else 0

        # Время запуска после задержки
        run_time = now + timedelta(seconds=delay)

        # Если после запуска будет больше минуты с первого запроса - обнуляем
        if run_time >= stream.first_call_minute + timedelta(seconds=60):
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

        print(
            f'Поток: {stream.name}, first_call: {stream.first_call_minute}, '
            f'next_call: {stream.next_call}, '
            f'calls: {stream.minute_calls}, delay: {delay}'
        )

        # Задержка до запроса (если есть)
        time.sleep(delay)

    def update_minute_limit(self, retry_after, stream) -> None:
        # Если нет минутного лимита - задаем
        if not self.api.minute_limit:
            self.api.minute_limit = stream.minute_calls

        self.change_next_call(datetime.now() + timedelta(seconds=retry_after),
                              stream)

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
            if response is None:
                stream.active = False
                db.session.commit()
                return

            # Проверка на превышение минутного лимита
            minute_limit = self.minute_limit_trigger(response)
            if minute_limit is not False:
                retry_after = minute_limit
                # Логи
                m = (f'Превышен лимит запросов в минуту'
                     f'(retry_after={retry_after}). {stream.name}')
                current_app.logger.warning(m, exc_info=True)
                self.logs.set('warning', m)

                # Уменьшить лимит
                self.update_minute_limit(retry_after, stream)
                continue

            # Проверка на превышение месячного лимита
            monthly_limit = self.monthly_limit_trigger(response)
            if monthly_limit is not False:
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
    # Неверная ссылка
    if not url.startswith('http'):
        return

    time.sleep(0.1)

    proxies = {}
    if stream:
        api.new_call(stream)

        # Прокси
        if stream.proxy:
            proxy = stream.proxy.replace('https://', 'http://')
            proxies = {'http': proxy, 'https': proxy}

    max_attempts = 3
    while max_attempts > 0:
        max_attempts -= 1

        try:
            return requests.get(url, proxies=proxies)

        except requests.exceptions.ConnectionError as e:
            m = f'{stream.name + ". " if stream else ""}Ошибка. {url}. {e}'
            current_app.logger.error(m, exc_info=True)
            api.logs.set('error', m)
            time.sleep(60)

        except Exception as e:
            m = f'{stream.name + ". " if stream else ""}Ошибка. {url}. {e}'
            current_app.logger.error(m, exc_info=True)
            api.logs.set('error', m)
            raise
