from datetime import datetime

from ..app import db, celery
from .utils import api_info, get_api, get_data, get_api_task, response_json, \
    api_logging, ApiName, task_logging, api_data
from . import models


API_NAME: ApiName = 'proxy'
BASE_URL: str = 'https://proxy6.net/api'


def get_proxies() -> dict:
    return api_data.get('proxy_list', API_NAME, dict)


@celery.task(bind=True, name='proxy_update', max_retries=None)
@task_logging
def proxy_update(self) -> None:

    api = get_api(API_NAME)
    api.update_streams()

    method = 'getproxy/?state=active'
    while True:
        # Получение данных
        data = get_data(lambda key: f'{BASE_URL}/{key}/{method}', api)
        data = response_json(data)
        if data and data.get('list'):
            break

        api_logging.set('error', 'Нет данных', API_NAME, self.name)

    # Сохранение данных
    data = data['list']
    # Не использовать прокси, если скоро закончится
    for _, proxy in data.items():
        proxy_end = datetime.strptime(proxy['date_end'], '%Y-%m-%d %H:%M:%S')
        time_left = (proxy_end - datetime.now()).total_seconds()
        need_time = 6*60*60  # По умолчанию 6 часов
        task = get_api_task(self.name)
        if task and task.retry_after():
            need_time = task.retry_after()
        if need_time > time_left:
            del data[proxy]

    api_data.set('proxy_list', data, API_NAME)

    # Обновление потоков
    update_streams()

    # Инфо
    api_info.set('Количество активных прокси', len(data), API_NAME)
    api_info.set('Прокси обновлены', datetime.now(), API_NAME)


def update_streams() -> None:
    for api in db.session.execute(db.select(models.Api)).scalars():
        api.update_streams()
    # Логи
    api_logging.set('info', 'Потоки обновлены', API_NAME)
