from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy.orm import Mapped, mapped_column

from portfolio_tracker.models import Base

from ..app import db

if TYPE_CHECKING:
    from werkzeug.datastructures.structures import ImmutableMultiDict


class Api(Base):
    __tablename__ = 'api'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: str = db.Column(db.String(32))
    need_key: bool = db.Column(db.Boolean)
    need_proxy: bool = db.Column(db.Boolean, default=True)
    minute_limit: int = db.Column(db.Integer, default=0)
    month_limit: int = db.Column(db.Integer, default=0)
    key_prefix: str = db.Column(db.String(32), default='')

    # Relationships
    keys: Mapped[List[Key]] = db.relationship(
        'Key', backref=db.backref('api', lazy=True))
    streams: Mapped[List[Stream]] = db.relationship(
        'Stream', backref=db.backref('api', lazy=True))

    @property
    def service(self):
        from portfolio_tracker.admin.services.api import ApiService
        return ApiService(self)



class Key(Base):
    __tablename__ = 'api_key'

    id: Mapped[int] = mapped_column(primary_key=True)
    api_id: Api.id = db.Column(db.Integer, db.ForeignKey('api.id'))
    api_key: str = db.Column(db.String(1024))
    comment: str = db.Column(db.Text)

    @property
    def service(self):
        from portfolio_tracker.admin.services.api import KeyService
        return KeyService(self)


class Stream(Base):
    __tablename__ = 'api_stream'

    id: Mapped[int] = mapped_column(primary_key=True)
    name = db.Column(db.String(128))
    api_id: Api.id = db.Column(db.Integer, db.ForeignKey('api.id'))
    api_key_id: Key.id = db.Column(db.Integer, db.ForeignKey('api_key.id'))
    proxy_id: str = db.Column(db.String(128))
    proxy: str = db.Column(db.String(256))
    month_calls: int = db.Column(db.Integer, default=0)
    minute_calls: int = db.Column(db.Integer, default=0)
    first_call_minute: datetime = db.Column(db.DateTime,
                                            default=datetime.now())
    first_call_month: datetime = db.Column(db.DateTime, default=datetime.now())
    next_call: datetime = db.Column(db.DateTime, default=datetime.now())
    active: bool = db.Column(db.Boolean, default=True)

    # Relationships
    key: Mapped[List[Key]] = db.relationship(
        'Key', backref=db.backref('stream', uselist=False, lazy=True))



class Task(Base):
    __tablename__ = 'api_task'

    name = db.Column(db.String(128), primary_key=True)
    retry_period_type: int = db.Column(db.Integer, default=0)
    retry_period_count: int = db.Column(db.Integer, default=0)

    @property
    def retry_after(self) -> int:
        return 60 * self.retry_period_type * self.retry_period_count  # секунды
