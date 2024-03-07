from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, Literal, TypeAlias

from portfolio_tracker.admin.integrations_api import ApiIntegration
from portfolio_tracker.general_functions import MARKETS

from ..portfolio.models import Ticker
from ..app import db
from . import integrations

if TYPE_CHECKING:
    pass


Events: TypeAlias = Literal['not_updated_prices', 'new_tickers',
                            'not_found_tickers', 'updated_images']


class MarketEvent(integrations.Event):
    def __init__(self, name):
        super().__init__(name)
        self.list: dict[Events, str] = {
            'not_updated_prices': 'Цены не обновлены',
            'new_tickers': 'Новые тикеры',
            'not_found_tickers': 'Тикеры не найдены',
            'updated_images': 'Обновлены картинки'
        }

    def update(self, ids_in_event: list[str], event_name: Events,
               exclude_missing: bool = True) -> None:
        today_str = str(datetime.now().date())

        # Прошлые данные
        ids_in_db = self.get(event_name, dict)

        # Добавление ненайденных
        for ticker_id in ids_in_event:
            ids_in_db.setdefault(ticker_id, [])
            if today_str not in ids_in_db[ticker_id]:
                ids_in_db[ticker_id].append(today_str)

        # Исключение найденных (отсутствующих в ids)
        if exclude_missing is True:
            for ticker_id in list(ids_in_db):
                if ticker_id not in ids_in_event:
                    del ids_in_db[ticker_id]

        if ids_in_db:
            # Сохранение данных
            self.set(event_name, ids_in_db)
        else:
            # Удаление события, если пусто
            self.delete(event_name)


class MarketIntegration(ApiIntegration):
    def __init__(self, name):
        if name not in MARKETS:
            return

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
