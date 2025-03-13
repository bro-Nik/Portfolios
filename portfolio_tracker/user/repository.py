from portfolio_tracker.repository import DefaultRepository
from .models import User
from ..app import login_manager, db


class UserRepository(DefaultRepository):
    """Репозиторий для управления пользователями в базе данных."""
    model = User

    @login_manager.user_loader
    @staticmethod
    def get(user_id: int | None = None, email: str | None = None) -> User | None:
        select = db.select(User)
        if user_id:
            select = select.filter_by(id=user_id)
        elif email:
            select = select.filter_by(email=email)
        else:
            return None
        return db.session.execute(select).scalar()

    @staticmethod
    def delete(user: User) -> None:
        if user.info:
            db.session.delete(user.info)

        db.session.delete(user)
        db.session.commit()

    @staticmethod
    def get_demo_user() -> User | None:
        return db.session.execute(db.select(User).filter_by(type='demo')).scalar()
