from datetime import datetime
import os

from flask import current_app

from portfolio_tracker.general_functions import remove_prefix
from portfolio_tracker.portfolio.models import PriceHistory, Ticker


class TickerService:

    def __init__(self, ticker: Ticker) -> None:
        self.ticker = ticker

    def edit(self, form: dict) -> None:
        self.ticker.id = form.get('id', '')
        self.ticker.symbol = form.get('symbol', '')
        self.ticker.name = form.get('name', '')
        self.ticker.stable = bool(form.get('stable'))

    def set_price(self, date: datetime.date, price: float) -> None:
        d = None
        for day in self.ticker.history:
            if day.date == date:
                d = day
                break

        if not d:
            d = PriceHistory(date=date)
            self.ticker.history.append(d)
        d.price_usd = price

    def external_url(self):
        external_id = remove_prefix(self.ticker.id, self.ticker.market)
        if self.ticker.market == 'crypto':
            url = 'https://www.coingecko.com/ru/%D0%9A%D1%80%D0%B8%D0%BF%D1%82%D0%BE%D0%B2%D0%B0%D0%BB%D1%8E%D1%82%D1%8B/'
            return f'{url}{external_id}'

    def delete(self) -> None:
        # Цены
        history = getattr(self.ticker, 'history', None)
        if history:
            from portfolio_tracker.portfolio.repository import PriceHistoryRepository
            for price in history:
                price.ticker_id = None
                PriceHistoryRepository.delete(price)
        # Активы
        if self.ticker.assets:
            for asset in self.ticker.assets:
                asset.service.delete()

        # Иконки
        # Папка хранения изображений
        if self.ticker.image:
            upload_folder = current_app.config['UPLOAD_FOLDER']
            path = f'{upload_folder}/images/tickers/{self.ticker.market}'
            try:
                os.remove(f'{path}/24/{self.ticker.image}')
                os.remove(f'{path}/40/{self.ticker.image}')
            except:
                pass

        from portfolio_tracker.portfolio.repository import TickerRepository
        TickerRepository.delete(self.ticker)
