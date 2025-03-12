from __future__ import annotations
from typing import TYPE_CHECKING
import requests
from werkzeug.security import generate_password_hash, check_password_hash

from flask_babel import gettext
from flask import request, current_app

from portfolio_tracker.general_functions import find_by_attr
from portfolio_tracker.portfolio.models import Portfolio
from portfolio_tracker.user.repository import UserRepository
from portfolio_tracker.wallet.models import Wallet
from portfolio_tracker.watchlist.models import Watchlist

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

    def delete(self) -> None:
        """Удалить пользователя и его данные."""

        self.cleare_data()
        UserRepository.delete(self.user)

    def cleare_data(self) -> None:
        """Очистить данные пользователя."""

        from portfolio_tracker.watchlist.repository import AlertRepository, AssetRepository
        for asset in self.user.watchlist:
            for alert in asset.alerts:
                AlertRepository.delete(alert)

            AssetRepository.delete(asset)

        from portfolio_tracker.wallet.repository import WalletAssetRepository, WalletRepository
        for wallet in self.user.wallets:
            for asset in wallet.assets:
                WalletAssetRepository.delete(asset)

            WalletRepository.delete(wallet)

        from portfolio_tracker.portfolio.repository import AssetRepository, TransactionRepository, BodyRepository, OtherTransactionRepository, OtherAssetRepository, PortfolioRepository
        for portfolio in self.user.portfolios:
            for asset in portfolio.assets:
                for transaction in asset.transactions:
                    TransactionRepository.delete(transaction)
                AssetRepository.delete(asset)

            for asset in portfolio.other_assets:
                for body in asset.bodies:
                    BodyRepository.delete(body)
                for transaction in asset.transactions:
                    OtherTransactionRepository.delete(transaction)
                OtherAssetRepository.delete(asset)

            PortfolioRepository.delete(portfolio)

    def change_currency(self, currency: str | None = None) -> None:
        """Изменить валюту пользователя."""
        if not currency:
            currency = 'usd'
        self.user.currency = currency
        prefix = current_app.config['CURRENCY_PREFIX']
        self.user.currency_ticker_id = f'{prefix}{currency}'

    def change_locale(self, locale: str | None = None) -> None:
        """Изменить локаль пользователя."""
        if not locale:
            locale = 'en'
        self.user.locale = locale

    def new_login(self) -> None:
        """Обработать новый логин пользователя и обновить данные о местоположении."""
        ip = request.headers.get('X-Real-IP')
        if ip:
            response = requests.get(f'http://ip-api.com/json/{ip}').json()
            if response.get('status') == 'success':
                self.user.info.country = response.get('country')
                self.user.info.city = response.get('city')
                UserRepository.save(self.user)

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
                a.service.set_default_data()

            for t in p.transactions:
                if t not in transactions:
                    transactions.append(t)

        for w in self.user.wallets:
            for a in w.assets:
                a.service.set_default_data()

            for t in w.transactions:
                if t not in transactions:
                    transactions.append(t)

        for t in transactions:
            t.service.update_dependencies()

    def create_portfolio(self) -> Portfolio:
        """Возвращает новый портфель"""
        portfolio = Portfolio()
        portfolio.user_id = self.user.id
        portfolio.user = self.user
        return portfolio

    def get_portfolio(self, portfolio_id: int | str | None) -> Portfolio | None:
        return find_by_attr(self.user.portfolios, 'id', portfolio_id)

    def create_wallet(self) -> Wallet:
        """Возвращает новый кошелек"""
        wallet = Wallet()
        wallet.user_id = self.user.id
        wallet.user = self.user
        return wallet

    def create_default_wallet(self) -> None:
        """Возвращает новый кошелек"""
        if not self.user.wallets:
            from portfolio_tracker.wallet.repository import WalletRepository
            wallet = self.create_wallet()
            wallet.name = gettext('Кошелек по умолчанию')
            WalletRepository.save(wallet)

    def get_wallet(self, wallet_id: int | str | None) -> Wallet | None:
        return find_by_attr(self.user.wallets, 'id', wallet_id)

    def get_watchlist(self) -> Watchlist:
        watchlist = Watchlist()
        watchlist.assets = self.user.watchlist
        return watchlist
