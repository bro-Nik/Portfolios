from __future__ import annotations

from portfolio_tracker.repository import DefaultRepository

from ..app import db
from .models import Asset, OtherAsset, OtherTransaction, Portfolio, \
    PriceHistory, Ticker, Transaction, OtherBody


class TickerRepository(DefaultRepository):
    model = Ticker

    @staticmethod
    def get_with_market_paginate(market, search: str = '', page: int = 1):
        """Выдает частями тикеры определенного рынка"""
        select = db.select(Ticker).where(Ticker.market == market)
        select = select.order_by(Ticker.market_cap_rank.is_(None),
                                 Ticker.market_cap_rank.asc())

        if search:
            select = select.filter(Ticker.name.contains(search) |
                                   Ticker.symbol.contains(search))

        return db.paginate(select, page=page, per_page=20, error_out=False)


class PortfolioRepository(DefaultRepository):
    model = Portfolio


class AssetRepository(DefaultRepository):
    model = Asset


class OtherAssetRepository(DefaultRepository):
    model = OtherAsset


class TransactionRepository(DefaultRepository):
    model = Transaction


class OtherTransactionRepository(DefaultRepository):
    model = OtherTransaction


class BodyRepository(DefaultRepository):
    model = OtherBody


class PriceHistoryRepository(DefaultRepository):
    model = PriceHistory
