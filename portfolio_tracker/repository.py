from __future__ import annotations
from typing import Iterable, Type, TypeVar
from sqlalchemy.orm import DeclarativeBase

from portfolio_tracker.app import db


ModelType = TypeVar('ModelType', bound=DeclarativeBase)


class DefaultRepository:
    """Базовый репозиторий для работы с моделями."""
    model: Type[ModelType] = None

    @classmethod
    def get(cls, obj_id) -> ModelType | None:
        if obj_id:
            return db.session.get(cls.model, obj_id)

    @classmethod
    def get_with_ids(cls, ids: list | None = None) -> Iterable[ModelType]:
        if not ids:
            return []

        select = db.select(cls.model).filter(cls.model.id.in_(ids))
        return db.session.execute(select).scalars()

    @staticmethod
    def save(obj: ModelType) -> None:
        if obj not in db.session:
            db.session.add(obj)
        db.session.commit()

    @staticmethod
    def delete(obj: ModelType) -> None:
        db.session.delete(obj)
        db.session.commit()
