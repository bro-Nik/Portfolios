

from portfolio_tracker.general_functions import find_by_attr
from portfolio_tracker.portfolio.repository import TickerRepository
from portfolio_tracker.watchlist.models import Watchlist, WatchlistAsset
from portfolio_tracker.watchlist.repository import AssetRepository


class WatchlistService:

    def __init__(self, watchlist: Watchlist) -> None:
        self.watchlist = watchlist

    def get_asset(self, ticker_id: str | int | None = None, id: str | int | None = None, **_):
        if ticker_id:
            return find_by_attr(self.watchlist.assets, 'ticker_id', ticker_id)
        if id:
            return find_by_attr(self.watchlist.assets, 'id', id)

    def create_asset(self, ticker_id: str | None, save: bool) -> WatchlistAsset | None:
        """Создает новый отслеживаемый актив"""
        if not self.get_asset(ticker_id):
            ticker = TickerRepository.get(ticker_id)
            if ticker:
                asset = AssetRepository.create()
                asset.ticker_id = ticker.id
                asset.ticker = ticker


                if save:
                    self.watchlist.assets.append(asset)
                    AssetRepository.save(asset)
                return asset
