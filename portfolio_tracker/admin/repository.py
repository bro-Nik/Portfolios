from __future__ import annotations

from portfolio_tracker.admin.models import Api, Key, Stream, Task
from portfolio_tracker.repository import DefaultRepository

from ..app import db


class ApiRepository(DefaultRepository):
    model = Api

    @staticmethod
    def get_by_name(name) -> None:
        return db.session.execute(db.select(Api).filter_by(name=name)).scalar()


class KeyRepository(DefaultRepository):
    model = Key


class StreamRepository(DefaultRepository):
    model = Stream


class TaskRepository(DefaultRepository):
    model = Task
