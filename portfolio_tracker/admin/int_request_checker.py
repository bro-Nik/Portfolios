from datetime import datetime
import os
import requests

from flask import current_app, request

from ..app import redis
from .integrations_other import OtherIntegration


MODULE_NAME = 'requests'


class RequestChecker(OtherIntegration):
    def new_error(self, error_code: int):

        # Получение IP
        ip = request.headers.get('X-Real-IP')

        # Логи
        m = f'{error_code} # {ip if ip else "IP не определен"} # {request.url}'
        current_app.logger.warning(m)
        request_checker.logs.set('warning', m)

        if not ip:
            return

        # Запись в Redis
        data = self.data.get(ip, dict)

        data.setdefault('ip', ip)
        data.setdefault('requests', 0)
        data.setdefault('countries', [])
        data.setdefault('cities', [])
        data['requests'] += 1

        # Определение локали
        response = requests.get(f'http://ip-api.com/json/{ip}').json()
        if response.get('status') == 'success':
            country = response.get('country')
            if country and country not in data['countries']:
                data['countries'].append(country)

            city = response.get('city')
            if city and city not in data['cities']:
                data['cities'].append(city)

        # Временная блокировка
        if data['requests'] >= 10:
            self.to_ban(data)

        self.data.set(ip, data)

    def to_ban(self, data: dict):
        # Папка хранения изображений
        folder = current_app.config['UPLOAD_FOLDER']
        path = f'{folder}/admin/'
        os.makedirs(path, exist_ok=True)
        path_file = os.path.join(path, 'black_list.txt')
        with open(path_file, 'w') as f:
            f.write(f"deny {data['ip']}\n")

        self.logs.set('warning', f"Новый ip в бан: {data['ip']}, "
                                 f"страна: {data.get('countries')}, "
                                 f"город: {data.get('cities')}")


request_checker = RequestChecker('requests')
