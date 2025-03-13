from flask import flash
from flask_babel import gettext

from portfolio_tracker.general_functions import find_by_attr
from portfolio_tracker.portfolio.repository import TickerRepository
from portfolio_tracker.wallet.models import Wallet, WalletAsset
from portfolio_tracker.wallet.repository import WalletAssetRepository, WalletRepository


class WalletService:

    def __init__(self, wallet: Wallet) -> None:
        self.wallet = wallet

    def edit(self, form: dict) -> None:
        name = form.get('name')
        comment = form.get('comment', '')

        if name is not None:
            user_wallets = self.wallet.user.wallets
            names = [i.name for i in user_wallets if i != self.wallet]
            if name in names:
                n = 2
                while str(name) + str(n) in names:
                    n += 1
                name = str(name) + str(n)

        if name:
            self.wallet.name = name

        self.wallet.comment = comment
        WalletRepository.save(self.wallet)

    def update_price(self) -> None:
        self.wallet.cost_now = 0
        self.wallet.buy_orders = 0

        for asset in self.wallet.assets:
            self.wallet.buy_orders += asset.buy_orders
            self.wallet.cost_now += asset.cost_now

    def get_asset(self, find_by: str | int | None):
        asset = None
        if find_by:
            try:
                asset = find_by_attr(self.wallet.assets, 'id', int(find_by))
            except ValueError:
                asset = find_by_attr(self.wallet.assets, 'ticker_id', find_by)
        return asset

    def create_asset(self, ticker_id: str | None) -> WalletAsset | None:
        if not self.get_asset(ticker_id):
            ticker = TickerRepository.get(ticker_id)
            if ticker:
                asset = WalletAsset()
                asset.ticker = ticker
                asset.ticker_id = ticker.id

                asset.service.set_default_data()
                asset.wallet = self.wallet
                asset.wallet_id = self.wallet.id
                WalletAssetRepository.save(asset)
                return asset

    def delete_if_empty(self) -> None:
        if self.wallet.is_empty:
            self.delete()
        else:
            flash(gettext('Кошелек %(name)s не пустой',
                          name=self.wallet.name), 'warning')

    def delete(self) -> None:
        for asset in self.wallet.assets:
            asset.service.delete()
        WalletRepository.delete(self.wallet)
