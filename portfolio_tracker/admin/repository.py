from __future__ import annotations

from portfolio_tracker.admin.models import Api

from ..app import db


class DefaultRepository:

    @classmethod
    def get_by_id(cls, obj_id):
        if obj_id:
            return db.session.get(cls, obj_id)

    @staticmethod
    def save(obj) -> None:
        if not obj in db.session:
            db.session.add(obj)
        db.session.commit()

    @staticmethod
    def delete(obj) -> None:
        db.session.delete(obj)
        db.session.commit()


class ApiRepository(DefaultRepository):

    @staticmethod
    def get_by_name(name) -> None:
        return db.session.execute(db.select(Api).filter_by(name=name)).scalar()

    @staticmethod
    def create(*_, **kwargs) -> Api:
        return Api(**kwargs)


class KeyRepository(DefaultRepository):
    pass


class StreamRepository(DefaultRepository):
    pass


class TaskRepository(DefaultRepository):
    pass
