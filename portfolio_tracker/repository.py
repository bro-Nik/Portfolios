from .app import db


class Repository:

    @staticmethod
    def save() -> None:
        """Сохранить сессию."""
        db.session.commit()

    @staticmethod
    def add(obj) -> None:
        """Сохранить изменения пользователя."""
        db.session.add(obj)

    @staticmethod
    def delete(obj) -> None:
        """Сохранить изменения пользователя."""
        db.session.delete(obj)
