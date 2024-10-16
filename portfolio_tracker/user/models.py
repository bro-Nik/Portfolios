from typing import List, TYPE_CHECKING
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy.orm import Mapped

from ..app import db

if TYPE_CHECKING:
    from portfolio_tracker.portfolio.models import Ticker, Portfolio
    from portfolio_tracker.wallet.models import Wallet
    from portfolio_tracker.watchlist.models import WatchlistAsset


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email: str = db.Column(db.String(255), nullable=False, unique=True)
    password: str = db.Column(db.String(255), nullable=False)
    type: str = db.Column(db.String(255))
    locale: str = db.Column(db.String(32))
    timezone: str = db.Column(db.String(32))
    currency: str = db.Column(db.String(32))
    currency_ticker_id: str = db.Column(db.String(32),
                                        db.ForeignKey('ticker.id'))

    # Relationships
    currency_ticker: Mapped['Ticker'] = db.relationship(
        'Ticker', uselist=False)
    portfolios: Mapped[List['Portfolio']] = db.relationship(
        'Portfolio', backref=db.backref('user', lazy=True))
    wallets: Mapped[List['Wallet']] = db.relationship(
        'Wallet', backref=db.backref('user', lazy=True))
    watchlist: Mapped[List['WatchlistAsset']] = db.relationship(
        'WatchlistAsset', backref=db.backref('user', lazy=True))
    info: Mapped['UserInfo'] = db.relationship(
        'UserInfo', backref=db.backref('user', lazy=True), uselist=False)


class UserInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey('user.id'))
    country: str = db.Column(db.String(255))
    city: str = db.Column(db.String(255))
    first_visit: datetime = db.Column(db.DateTime,
                                      default=datetime.now(timezone.utc))
    last_visit: datetime = db.Column(db.DateTime,
                                     default=datetime.now(timezone.utc))
