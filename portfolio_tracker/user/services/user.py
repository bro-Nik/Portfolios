from __future__ import annotations
from typing import TYPE_CHECKING
import requests
from werkzeug.security import generate_password_hash, check_password_hash

from flask_babel import gettext
from flask import request, current_app
from flask_login import current_user

from portfolio_tracker.repository import Repository

if TYPE_CHECKING:
    from ..models import User


class UserService:
    """Сервис для управления пользователем."""

    def __init__(self, user: User) -> None:
        self.user = user

    def set_password(self, password: str) -> None:
        """Установить новый пароль."""
        self.user.password = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Проверить правильность пароля."""
        return check_password_hash(self.user.password, password)

    def is_authenticated(self):
        """Проверить, аутентифицирован ли пользователь."""
        return self.user.is_authenticated

    def is_demo(self) -> bool:
        """Проверить, является ли пользователь демо-аккаунтом."""
        return self.user.type == 'demo'

    def delete(self) -> None:
        """Удалить пользователя и его данные."""

        self.cleare_data()
        if self.user.info:
            Repository.delete(self.user.info)
        Repository.delete(self.user)

    def cleare_data(self) -> None:
        """Очистить данные пользователя."""
        for asset in self.user.watchlist:
            for alert in asset.alerts:
                Repository.delete(alert)
            Repository.delete(asset)

        for wallet in self.user.wallets:
            for asset in wallet.assets:
                Repository.delete(asset)
            Repository.delete(wallet)

        for portfolio in self.user.portfolios:
            for asset in portfolio.assets:
                for transaction in asset.transactions:
                    Repository.delete(transaction)
                Repository.delete(asset)

            for asset in portfolio.other_assets:
                for body in asset.bodies:
                    Repository.delete(body)
                for transaction in asset.transactions:
                    Repository.delete(transaction)
                Repository.delete(asset)
            Repository.delete(portfolio)


    def change_currency(self, currency: str = 'usd') -> None:
        """Изменить валюту пользователя."""
        self.user.currency = currency
        prefix = current_app.config['CURRENCY_PREFIX']
        self.user.currency_ticker_id = f'{prefix}{currency}'

    def change_locale(self, locale: str = 'en') -> None:
        """Изменить локаль пользователя."""
        self.user.locale = locale

    def new_login(self) -> None:
        """Обработать новый логин пользователя и обновить данные о местоположении."""
        ip = request.headers.get('X-Real-IP')
        if ip:
            response = requests.get(f'http://ip-api.com/json/{ip}').json()
            if response.get('status') == 'success':
                self.user.info.country = response.get('country')
                self.user.info.city = response.get('city')
                Repository.save()

    def make_admin(self) -> None:
        """Присвоить статус администратора."""
        self.user.type = 'admin'

    def unmake_admin(self) -> None:
        """Снять статус администратора."""
        self.user.type = ''

    def recalculate(self) -> None:
        """Пересчитать транзакции и обновить активы пользователя."""
        transactions = []
        for p in self.user.portfolios:
            for a in p.assets:
                a.set_default_data()

            for t in p.transactions:
                if t not in transactions:
                    transactions.append(t)

        for w in self.user.wallets:
            for a in w.assets:
                a.set_default_data()

            for t in w.transactions:
                if t not in transactions:
                    transactions.append(t)

        for t in transactions:
            t.update_dependencies()
