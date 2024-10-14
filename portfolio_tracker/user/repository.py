from .models import User, db

from ..app import login_manager


class UserRepository:

    @login_manager.user_loader
    @staticmethod
    def get(user_id: int | None = None, email: str | None = None) -> User:
        """Найти пользователя по ID или Email."""
        select = db.select(User)
        if user_id:
            select = select.filter_by(id=user_id)
        else:
            select = select.filter_by(email=email)
        return db.session.execute(select).scalar()

    @staticmethod
    def create(email: str) -> User:
        """Сохранить изменения пользователя."""
        return User(email=email)

    @staticmethod
    def get_demo_user() -> User | None:
        return db.session.execute(db.select(User).filter_by(type='demo')).scalar()
