from flask import flash
from flask_babel import gettext

from portfolio_tracker.general_functions import find_by_attr

from ..models import Asset, OtherAsset, Portfolio
from ..repository import AssetRepository, OtherAssetRepository, PortfolioRepository, TickerRepository


class PortfolioService:

    def __init__(self, portfolio: Portfolio) -> None:
        self.portfolio = portfolio

    def edit(self, form: dict) -> None:
        market = form.get('market')
        name = form.get('name')
        comment = form.get('comment')
        percent = form.get('percent')

        if not self.portfolio.market:
            if market in ('crypto', 'stocks', 'other'):
                self.portfolio.market = market
            else:
                return

        if name:
            # Поиск на дубликат имени и присвоение номера
            portfolios = self.portfolio.user.portfolios

            names = [i.name for i in portfolios if (i.market == self.portfolio.market
                                                    and i.id != self.portfolio.id)]
            if name in names:
                n = 2
                while f'{name}{n}' in names:
                    n += 1
                name = f'{name}{n}'

        if name:
            self.portfolio.name = name

        self.portfolio.percent = percent or 0
        self.portfolio.comment = comment or ''
        PortfolioRepository.save(self.portfolio)

    def update_info(self) -> None:
        self.portfolio.cost_now = 0
        self.portfolio.amount = 0
        self.portfolio.buy_orders = 0
        self.portfolio.invested = 0

        prefix = 'other_' if self.portfolio.market == 'other' else ''
        for asset in getattr(self.portfolio, f'{prefix}assets'):
            self.portfolio.cost_now += asset.cost_now
            self.portfolio.amount += asset.amount
            self.portfolio.invested += asset.amount if asset.amount > 0 else 0
            if self.portfolio.market != 'other':
                self.portfolio.buy_orders += asset.buy_orders

    def get_asset(self, find_by: str | int | None, create=False):
        asset = None
        if find_by:
            if getattr(self.portfolio, 'market') == 'other':
                try:
                    asset = find_by_attr(self.portfolio.other_assets, 'id', int(find_by))
                except ValueError:
                    asset = None
            else:
                try:
                    asset = find_by_attr(self.portfolio.assets, 'id', int(find_by))
                except ValueError:
                    asset = find_by_attr(self.portfolio.assets, 'ticker_id', find_by)

        if not asset and create is True:
            asset = self.create_asset(ticker_id=str(find_by))
        return asset

    def _create_market_asset(self, ticker_id: str | None) -> Asset | None:
        """Создает новый цифровой актив"""
        if not self.get_asset(ticker_id):
            # TickerRepository = DefaultRepository(model=Ticker)
            ticker = TickerRepository.get(ticker_id)
            if ticker and ticker.market == self.portfolio.market:
                asset = Asset()
                asset.ticker_id = ticker.id
                asset.ticker = ticker
                asset.portfolio = self.portfolio

                asset.service.set_default_data()
                AssetRepository.save(asset)
                return asset

    def _create_other_asset(self) -> OtherAsset | None:
        """Создает новый прочий актив"""
        asset = OtherAsset()
        asset.portfolio = self.portfolio
        OtherAssetRepository.save(asset)
        return asset

    def create_asset(self, ticker_id: str | None) -> Asset | OtherAsset | None:
        """Возвращает новый актив"""
        if self.portfolio.market == 'other':
            return self._create_other_asset()

        return self._create_market_asset(ticker_id)

    def delete_if_empty(self) -> None:
        if self.portfolio.is_empty:
            self.delete()
        else:
            flash(gettext('Портфель %(name)s не пуст',
                          name=self.portfolio.name), 'warning')

    def delete(self) -> None:
        prefix = 'other_' if self.portfolio.market == 'other' else ''
        for asset in getattr(self.portfolio, f'{prefix}assets'):
            asset.service.delete()
        PortfolioRepository.delete(self.portfolio)
