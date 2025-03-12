from __future__ import annotations
from typing import List
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models import Base
from ..portfolio.models import Ticker, Transaction


class WatchlistAsset(Base):
    __tablename__ = "watchlist_asset"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'))
    ticker_id: Mapped[str] = mapped_column(String(32), ForeignKey("ticker.id"))
    comment: Mapped[str] = mapped_column()

    # Relationships
    user: Mapped['User'] = relationship(back_populates="watchlist")
    ticker: Mapped['Ticker'] = relationship(uselist=False)
    alerts: Mapped[List['Alert']] = relationship(back_populates='watchlist_asset', lazy=True)

    @property
    def service(self):
        from portfolio_tracker.watchlist.services.asset import AssetService
        return AssetService(self)

    @property
    def is_empty(self) -> bool:
        return not (self.alerts or self.comment)

    @property
    def price(self):
        return self.ticker.price

class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))
    asset_id: Mapped[int | str | None] = mapped_column(Integer, ForeignKey("asset.id"))
    watchlist_asset_id: Mapped[int] = mapped_column(ForeignKey("watchlist_asset.id"))
    price: Mapped[float] = mapped_column()
    price_usd: Mapped[float] = mapped_column()
    price_ticker_id: Mapped[str] = mapped_column(String(32), ForeignKey("ticker.id"))
    type: Mapped[str] = mapped_column(String(24))
    comment: Mapped[str] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(24), default='on')
    transaction_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("transaction.id"))

    # Relationships
    asset: Mapped['Asset'] = relationship(back_populates='alerts', lazy=True)
    transaction: Mapped['Transaction'] = relationship(back_populates='alert', uselist=False)
    price_ticker: Mapped['Ticker'] = relationship(uselist=False)
    watchlist_asset: Mapped['WatchlistAsset'] = relationship(uselist=False)

    @property
    def service(self):
        from portfolio_tracker.watchlist.services.alert import AlertService
        return AlertService(self)


class Watchlist:
    def __init__(self):
        self.assets = []

    @property
    def service(self):
        from portfolio_tracker.watchlist.services.watchlist import WatchlistService
        return WatchlistService(self)
