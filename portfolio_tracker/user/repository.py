from .models import User, db

from ..app import login_manager


class UserRepository:
    """Репозиторий для управления пользователями в базе данных.

    Этот класс предоставляет методы для создания пользователей,
    получения пользователей по ID или Email, а также получения демо-пользователя.

    """

    @login_manager.user_loader
    @staticmethod
    def get(user_id: int | None = None, email: str | None = None) -> User | None:
        """Получить пользователя по ID или Email.

        Параметры:
            user_id (int | None): ID пользователя, если известен.
            email (str | None): Email пользователя, если известен.

        Возвращает:
            User | None: Объект пользователя, если найден, иначе None.
        """

        select = db.select(User)
        if user_id:
            select = select.filter_by(id=user_id)
        elif email:
            select = select.filter_by(email=email)
        else:
            return None
        return db.session.execute(select).scalar()

    @staticmethod
    def create(email: str) -> User:
        """Создать нового пользователя без сохранения его в базе данных.

        Параметры:
            email (str): Email нового пользователя.

        Возвращает:
            User: Объект созданного пользователя.

        """

        return User(email=email)

    @staticmethod
    def get_demo_user() -> User | None:
        """Получить демо-пользователя.

        Возвращает:
            User | None: Объект демо-пользователя, если найден, иначе None.
        """

        return db.session.execute(db.select(User).filter_by(type='demo')).scalar()
