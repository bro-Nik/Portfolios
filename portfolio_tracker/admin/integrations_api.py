from __future__ import annotations
from datetime import datetime, timedelta
import time
from typing import TYPE_CHECKING, Callable, Literal, TypeAlias
import requests

from flask import current_app

from ..portfolio.models import Ticker
from ..app import db, redis
from .models import Api, Stream
from . import integrations

if TYPE_CHECKING:
    pass


ApiName: TypeAlias = Literal['crypto', 'stocks', 'currency', 'proxy']
API_NAMES: tuple[ApiName, ...] = ('crypto', 'stocks', 'currency', 'proxy')
Events: TypeAlias = Literal['not_updated_prices', 'new_tickers',
                            'not_found_tickers', 'updated_images']


class ApiIntegration(integrations.Integration):
    def __init__(self, name: str | None):
        super().__init__(name)

        if name not in API_NAMES:
            return

        api = db.session.execute(db.select(Api).filter_by(name=name)).scalar()
        if not api:
            api = Api(name=name)
            db.session.add(api)
        self.api = api
        # self.type = 'api'
        # if api.id:
        #     self.update_streams()

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
            # proxies = {'https': stream.proxy.replace('http://', 'https://'),
            #            'http': stream.proxy.replace('https://', 'http://')}
            proxies = {'http': stream.proxy.replace('https://', 'http://')}

    try:
        return requests.get(url, proxies=proxies)

    except requests.exceptions.ConnectionError as e:
        current_app.logger.error(f'Ошибка: {e}', exc_info=True)
        api.logs.set('error', f'Ошибка: {e}')

    except Exception as e:
        current_app.logger.error(f'Ошибка: {e}. url: {url}', exc_info=True)
        api.logs.set('error', f'Ошибка: {e}')
        raise


class MarketEvent(integrations.Event):
    def __init__(self, name):
        super().__init__(name)
        self.list: dict[Events, str] = {
            'not_updated_prices': 'Цены не обновлены',
            'new_tickers': 'Новые тикеры',
            'not_found_tickers': 'Тикеры не найдены',
            'updated_images': 'Обновлены картинки'
        }

    def update(self, ids_in_event: list[Ticker.id],
               event_name: str, exclude_missing: bool = True) -> None:
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


class MarketIntegration(ApiIntegration):
    def __init__(self, name):
        super().__init__(name)
        self.events = MarketEvent(name)

    def evets_info(self, event):
        ids = []
        data = {'events': {}}

        # Общие действия
        for event_name, event_name_ru in self.events.list.items():
            data_event = self.events.get(event_name, dict)
            if data_event:
                data['events'][event_name_ru] = data_event

            # для списка тикеров
            if event_name == event:
                ids = data['events'][event_name_ru].keys()

        data['tickers'] = db.session.execute(
            db.select(Ticker).filter(Ticker.id.in_(ids))).scalars()
        return data
