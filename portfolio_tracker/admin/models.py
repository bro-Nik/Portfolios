from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy.orm import Mapped

from ..app import db

if TYPE_CHECKING:
    from werkzeug.datastructures.structures import ImmutableMultiDict
    from .api_integration import ApiName


class Api(db.Model):
    __tablename__ = 'api'

    id = db.Column(db.Integer, primary_key=True)
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

    def edit(self, form: ImmutableMultiDict) -> None:
        self.minute_limit = form.get('minute_limit', 0, type=int)
        self.month_limit = form.get('month_limit', 0, type=int)
        self.key_prefix = form.get('key_prefix', '', type=str)
        self.need_key = form.get('need_key', False, type=bool)
        self.need_proxy = form.get('need_proxy', False, type=bool)
        db.session.commit()


class Key(db.Model):
    __tablename__ = 'api_key'
    # __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    api_id: Api.id = db.Column(db.Integer, db.ForeignKey('api.id'))
    api_key: str = db.Column(db.String(1024))
    comment: str = db.Column(db.Text)

    # Relationships
    # api: Mapped[Api]
    # stream: Mapped[ApiStream]

    def edit(self, form: ImmutableMultiDict) -> None:
        if not self.id:
            db.session.add(self)
        self.api_key = form['api_key']
        self.comment = form['comment']
        db.session.commit()


class Stream(db.Model):
    __tablename__ = 'api_stream'
    # __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
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
    # api: Mapped[Api]


class Task(db.Model):
    __tablename__ = 'api_task'

    name = db.Column(db.String(128), primary_key=True)
    api_name: ApiName = db.Column(db.String(32))
    retry_period_type: int = db.Column(db.Integer, default=0)
    retry_period_count: int = db.Column(db.Integer, default=0)

    def edit(self, form: ImmutableMultiDict) -> None:
        self.retry_period_type = form.get('retry_period_type', 0, type=int)
        self.retry_period_count = form.get('retry_period_count', 0, type=int)
        db.session.commit()

    def retry_after(self) -> int:
        return 60 * self.retry_period_type * self.retry_period_count  # секунды
