from sqlalchemy import func

from portfolio_tracker.models import Ticker, User
from portfolio_tracker.app import db


def get_tickers(market=None):
    select = db.select(Ticker).order_by(Ticker.market_cap_rank.is_(None),
                                        Ticker.market_cap_rank.asc())
    if market:
        select = select.filter_by(market=market)
    return db.session.execute(select).scalars()


def get_user(id):
    if id:
        return db.session.execute(db.select(User).filter_by(id=id)).scalar()


def get_ticker(id):
    if id:
        return db.session.execute(db.select(Ticker).filter_by(id=id)).scalar()


def task_state(task):
    if task.id:
        if task.state in ['WORK']:
            return 'Работает'
        elif task.state in ['RETRY']:
            return 'Ожидает'
        elif task.state == 'LOADING':
            return 'Загрузка'
        elif task.state == 'REVOKED':
            return 'Остановлено'
        elif task.state == 'SUCCESS':
            return 'Готово'
        elif task.state == 'FAILURE':
            return 'Ошибка'
        else:
            return task.state
    else:
        return ''


def get_tickers_count(market):
    return db.session.execute(db.select(func.count()).select_from(Ticker)
                              .filter_by(market=market)).scalar()


def get_users_count(type=None):
    select = db.select(func.count()).select_from(User)
    if type:
        select = select.filter_by(type=type)
    return db.session.execute(select).scalar()
