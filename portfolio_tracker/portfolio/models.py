from __future__ import annotations
from datetime import datetime, date
from typing import List

from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import Mapped, backref
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from ..models import Base
from ..mixins import AssetMixin, DetailsMixin


class Transaction(Base):
    __tablename__ = "transaction"

    date: Mapped[datetime] = mapped_column()
    ticker_id: Mapped[str] = mapped_column(String(32), ForeignKey("ticker.id"))
    ticker2_id: Mapped[str] = mapped_column(String(32), ForeignKey("ticker.id"))
    quantity: Mapped[float] = mapped_column()
    quantity2: Mapped[float] = mapped_column()
    price: Mapped[float] = mapped_column()
    price_usd: Mapped[float] = mapped_column()
    type: Mapped[str] = mapped_column(String(24))
    comment: Mapped[str] = mapped_column(String(1024))
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallet.id"))
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolio.id"))
    order: Mapped[bool] = mapped_column(default=False)
    related_transaction_id: Mapped[int] = mapped_column(ForeignKey("transaction.id"))

    # Relationships
    alert: Mapped['Alert'] = relationship(back_populates='transaction', lazy=True)
    portfolio: Mapped['Portfolio'] = relationship(back_populates='transactions', lazy=True)
    wallet: Mapped['Wallet'] = relationship(back_populates='transactions', lazy=True)
    base_ticker: Mapped['Ticker'] = relationship(foreign_keys=[ticker_id], viewonly=True)
    quote_ticker: Mapped['Ticker'] = relationship(foreign_keys=[ticker2_id], viewonly=True)
    related_transaction: Mapped['Transaction'] = relationship(foreign_keys=[related_transaction_id], uselist=False)

    @property
    def service(self):
        from .services.transaction import TransactionService
        return TransactionService(self)


class Asset(Base, DetailsMixin, AssetMixin):
    __tablename__ = "asset"

    ticker_id: Mapped[str] = mapped_column(String(256), ForeignKey("ticker.id"))
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolio.id"))
    quantity: Mapped[float] = mapped_column(default=0)
    buy_orders: Mapped[float] = mapped_column(default=0)
    sell_orders: Mapped[float] = mapped_column(default=0)
    amount: Mapped[float] = mapped_column(default=0)
    percent: Mapped[float] = mapped_column(default=0)
    comment: Mapped[str] = mapped_column(String(1024))

    # Relationships
    portfolio: Mapped['Portfolio'] = relationship(back_populates='assets', lazy=True)
    ticker: Mapped['Ticker'] = relationship(foreign_keys=ticker_id, back_populates="assets", lazy=True)
    transactions: Mapped[List['Transaction']] = relationship(
        "Transaction",
        primaryjoin="and_(or_(Asset.ticker_id == foreign(Transaction.ticker_id), Asset.ticker_id == foreign(Transaction.ticker2_id)), "
                    "Asset.portfolio_id == Transaction.portfolio_id)",
        backref=backref('portfolio_asset', lazy=True)
    )
    alerts: Mapped[List['Alert']] = relationship(
        primaryjoin="Asset.id == foreign(Alert.asset_id)"
    )

    @property
    def service(self):
        from .services.asset import AssetService
        return AssetService(self)

    @property
    def average_buy_price(self) -> float:
        return self.amount / self.quantity if self.quantity and self.amount > 0 else 0


class OtherAsset(Base, DetailsMixin):
    __tablename__ = "other_asset"

    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolio.id"))
    name: Mapped[str] = mapped_column(String(255))
    percent: Mapped[float] = mapped_column(default=0)
    amount: Mapped[float] = mapped_column(default=0)
    cost_now: Mapped[float] = mapped_column(default=0)
    comment: Mapped[str] = mapped_column(String(1024), default='')

    # Relationships
    portfolio: Mapped['Portfolio'] = relationship(back_populates='other_assets', lazy=True)
    transactions: Mapped[List['OtherTransaction']] = relationship(back_populates="portfolio_asset", lazy=True)
    bodies: Mapped[List['OtherBody']] = relationship(back_populates="asset", lazy=True)

    @property
    def service(self):
        from portfolio_tracker.portfolio.services.asset import OtherAssetService
        return OtherAssetService(self)

    @property
    def is_empty(self) -> bool:
        return not (self.bodies or self.transactions or self.comment)


class OtherTransaction(Base):
    __tablename__ = "other_transaction"

    date: Mapped[datetime] = mapped_column()
    asset_id: Mapped[int] = mapped_column(ForeignKey("other_asset.id"))
    amount: Mapped[float] = mapped_column(default=0)
    amount_ticker_id: Mapped[str] = mapped_column(String(32), ForeignKey("ticker.id"))
    amount_usd: Mapped[float] = mapped_column(default=0)
    type: Mapped[str] = mapped_column(String(24))
    comment: Mapped[str] = mapped_column(String(1024))

    # Relationships
    amount_ticker: Mapped['Ticker'] = relationship(uselist=False)
    portfolio_asset: Mapped['OtherAsset'] = relationship(back_populates="transactions", lazy=True)

    @property
    def service(self):
        from portfolio_tracker.portfolio.services.other_transaction import OtherTransactionService
        return OtherTransactionService(self)


class OtherBody(Base):
    __tablename__ = "other_body"

    name: Mapped[str] = mapped_column(String(255))
    date: Mapped[datetime] = mapped_column()
    asset_id: Mapped[int] = mapped_column(ForeignKey("other_asset.id"))
    amount: Mapped[float] = mapped_column(default=0)
    amount_usd: Mapped[float] = mapped_column(default=0)
    amount_ticker_id: Mapped[str] = mapped_column(String(32), ForeignKey("ticker.id"))
    cost_now: Mapped[float] = mapped_column(default=0)
    cost_now_usd: Mapped[float] = mapped_column(default=0)
    cost_now_ticker_id: Mapped[str] = mapped_column(String(32), ForeignKey("ticker.id"))
    comment: Mapped[str] = mapped_column(String(1024))

    # Relationships
    amount_ticker: Mapped['Ticker'] = relationship(foreign_keys=[amount_ticker_id], viewonly=True)
    cost_now_ticker: Mapped['Ticker'] = relationship(foreign_keys=[cost_now_ticker_id], viewonly=True)
    asset: Mapped['OtherAsset'] = relationship(back_populates="bodies", lazy=True)

    @property
    def service(self):
        from portfolio_tracker.portfolio.services.other_body import OtherBodyService
        return OtherBodyService(self)


class Ticker(Base):
    __tablename__ = "ticker"

    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    name: Mapped[str] = mapped_column(String(1024))
    symbol: Mapped[str] = mapped_column(String(124))
    image: Mapped[str | None] = mapped_column(String(1024))
    market_cap_rank: Mapped[int | None] = mapped_column()
    price: Mapped[float] = mapped_column(default=0)
    market: Mapped[str] = mapped_column(String(32))
    stable: Mapped[bool] = mapped_column()

    assets: Mapped[List['Asset']] = relationship()
    history: Mapped['PriceHistory'] = relationship(back_populates="ticker", lazy=True)


class Portfolio(Base, DetailsMixin):
    __tablename__ = "portfolio"

    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'))
    market: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255))
    comment: Mapped[str] = mapped_column(String(1024))
    percent: Mapped[float] = mapped_column(default=0)

    # Relationships
    user: Mapped['User'] = relationship(back_populates="portfolios")
    assets: Mapped[List['Asset']] = relationship(back_populates="portfolio", lazy=True)
    other_assets: Mapped[List['OtherAsset']] = relationship(back_populates="portfolio", lazy=True)
    transactions: Mapped[List['Transaction']] = relationship(back_populates="portfolio", lazy=True)

    @property
    def service(self):
        from portfolio_tracker.portfolio.services.portfolio import PortfolioService
        return PortfolioService(self)

    @property
    def is_empty(self) -> bool:
        return not (self.assets or self.other_assets or self.comment)


class PriceHistory(Base):
    __tablename__ = "price_history"

    date: Mapped[date] = mapped_column(primary_key=True)
    ticker_id: Mapped[str] = mapped_column(String(32), ForeignKey("ticker.id"), primary_key=True)
    price_usd: Mapped[float] = mapped_column()

    # Relationships
    ticker: Mapped['Ticker'] = relationship(back_populates="history", lazy=True)
