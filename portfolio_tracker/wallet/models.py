from __future__ import annotations
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from portfolio_tracker.portfolio.models import Transaction
from ..models import Base
from ..mixins import AssetMixin


if TYPE_CHECKING:
    from ..portfolio.models import Ticker


class Wallet(Base):
    __tablename__ = "wallet"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'))
    name: Mapped[str] = mapped_column(String(255))
    comment: Mapped[str | None] = mapped_column(String(1024))

    user: Mapped['User'] = relationship(back_populates='wallets')
    assets: Mapped[List['WalletAsset']] = relationship(back_populates="wallet")
    transactions: Mapped[List['Transaction']] = relationship(back_populates='wallet', lazy=True,
                                          order_by='Transaction.date.desc()')

    @property
    def is_empty(self) -> bool:
        return not (self.assets or self.transactions or self.comment)

    @property
    def service(self):
        from portfolio_tracker.wallet.services.wallet import WalletService
        return WalletService(self)


class WalletAsset(Base, AssetMixin):
    __tablename__ = "wallet_asset"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker_id: Mapped[str] = mapped_column(String(256), ForeignKey("ticker.id"))
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallet.id"))
    quantity: Mapped[float] = mapped_column(default=0)
    buy_orders: Mapped[float] = mapped_column(default=0)
    sell_orders: Mapped[float] = mapped_column(default=0)

    wallet: Mapped["Wallet"] = relationship(back_populates="assets")

    # Relationships
    ticker: Mapped[Ticker] = relationship(back_populates='', lazy=True)
    transactions: Mapped[List[Transaction]] = relationship(
        "Transaction",
        primaryjoin="and_(or_(WalletAsset.ticker_id == foreign(Transaction.ticker_id),"
                    "WalletAsset.ticker_id == foreign(Transaction.ticker2_id)),"
                    "WalletAsset.wallet_id == foreign(Transaction.wallet_id))",
        viewonly=True,
        backref=backref('wallet_asset', lazy=True)
    )

    @property
    def service(self):
        from portfolio_tracker.wallet.services.asset import AssetService
        return AssetService(self)
