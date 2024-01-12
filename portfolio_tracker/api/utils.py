from datetime import datetime

from sqlalchemy import func
from flask_login import current_user

from portfolio_tracker.models import db, Alert, WatchlistAsset, User


def update_user_last_visit() -> None:
    if current_user.is_authenticated and current_user.info:
        current_user.info.last_visit = datetime.utcnow()
        db.session.commit()


def get_worked_alerts_count() -> int | None:
    return db.session.execute(
        db.select(func.count()).select_from(User).
        filter(User.id == current_user.id).join(User.watchlist).
        join(WatchlistAsset.alerts).filter(Alert.status == 'worked')).scalar()
