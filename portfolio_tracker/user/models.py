from typing import List, TYPE_CHECKING
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from portfolio_tracker.models import Base


if TYPE_CHECKING:
    from portfolio_tracker.portfolio.models import Ticker, Portfolio
    from portfolio_tracker.wallet.models import Wallet
    from portfolio_tracker.watchlist.models import WatchlistAsset


class User(Base, UserMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str | None] = mapped_column(String(255))
    locale: Mapped[str | None] = mapped_column(String(32))
    timezone: Mapped[str | None] = mapped_column(String(32))
    currency: Mapped[str | None] = mapped_column(String(32))
    currency_ticker_id: Mapped[str | None] = mapped_column(String(32), ForeignKey('ticker.id'))

    # Relationships
    currency_ticker: Mapped['Ticker'] = relationship(uselist=False)
    portfolios: Mapped[List['Portfolio']] = relationship(back_populates='user', lazy=True)
    wallets: Mapped[List['Wallet']] = relationship(back_populates='user', lazy=True)
    watchlist: Mapped[List['WatchlistAsset']] = relationship(back_populates='user', lazy=True)
    info: Mapped['UserInfo'] = relationship(back_populates='user', lazy=True, uselist=False)

    @property
    def service(self):
        from portfolio_tracker.user.services.user import UserService
        return UserService(self)

    @property
    def is_demo(self) -> bool:
        """Проверить, является ли пользователь демо-аккаунтом."""
        return self.type == 'demo'


class UserInfo(Base):
    __tablename__ = "user_info"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'))
    country: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(255))
    first_visit: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))
    last_visit: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))

    user: Mapped['User'] = relationship(back_populates="info")
