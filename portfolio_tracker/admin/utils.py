from datetime import datetime
import pickle
from flask import current_app
from sqlalchemy import func

from portfolio_tracker.models import Ticker, User
from portfolio_tracker.app import db, redis


def get_prefix(market):
    return current_app.config[f'{market.upper()}_PREFIX']


def task_log_name(market):
    return f"task-log-{market}"


def get_task_log(market):
    key = task_log_name(market)
    log = redis.get(key)
    return pickle.loads(log) if log else []


def task_log(text, market):
    key = task_log_name(market)
    log = get_task_log(market)
    log.append({'text': text, 'time': datetime.utcnow()})
    redis.set(key, pickle.dumps(log))


def remove_prefix(ticker_id, market):
    prefix = get_prefix(market)
    if ticker_id.startswith(prefix):
        ticker_id = ticker_id[len(prefix):]

    return ticker_id


def add_prefix(ticker_id, market):
    return (get_prefix(market) + ticker_id).lower()


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
