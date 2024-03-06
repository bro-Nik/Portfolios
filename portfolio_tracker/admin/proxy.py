from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING

from flask import current_app

from ..app import celery
from .integrations import get_api_task, task_logging
from .integrations_api import API_NAMES, ApiIntegration, ApiName

if TYPE_CHECKING:
    import requests


API_NAME: ApiName = 'proxy'
BASE_URL: str = 'https://proxy6.net/api'


class Api(ApiIntegration):
    def response_processing(self, response: requests.models.Response | None,
                            ) -> dict | None:
        if response:
            # Ответ с данными
            if response.status_code == 200:
                return response.json()

            # Ошибки
            m = f'Ошибка, Код: {response.status_code}, {response.url}'
            self.logs.set('warning', m)
            current_app.logger.warning(m, exc_info=True)


def get_proxies() -> dict:
    api = Api(API_NAME)
    return api.data.get('proxy_list', dict)


@celery.task(bind=True, name='proxy_update', max_retries=None)
@task_logging
def proxy_update(self) -> None:

    api = Api(API_NAME)
    method = 'getproxy/?state=active'
    while True:
        # Получение данных
        response = api.request(lambda key: f'{BASE_URL}/{key}/{method}')
        data = api.response_processing(response)
        if data and data.get('list'):
            data = data['list']
            break

        api.logs.set('error', 'Нет данных', self.name)

    # Сохранение данных
    # Не использовать прокси, если скоро закончится
    for _, proxy in list(data.items()):

        proxy_end = datetime.strptime(proxy['date_end'], '%Y-%m-%d %H:%M:%S')
        time_left = (proxy_end - datetime.now()).total_seconds()
        need_time = 6*60*60  # По умолчанию 6 часов
        task = get_api_task(self.name)
        if task and task.retry_after():
            need_time = task.retry_after()
        if need_time > time_left:
            del data[proxy['id']]

    api.data.set('proxy_list', data)

    # Обновление потоков
    update_streams()

    # Инфо
    api.info.set('Количество активных прокси', len(data))
    api.info.set('Прокси обновлены', datetime.now())


def update_streams() -> None:
    for api_name in API_NAMES:
        api = ApiIntegration(api_name)
        api.update_streams()
    # Логи
    api = ApiIntegration(API_NAME)
    api.logs.set('info', 'Потоки обновлены')
