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


def get_tickers(market=None, without_image=None):
    select = db.select(Ticker).order_by(Ticker.market_cap_rank.is_(None),
                                        Ticker.market_cap_rank.asc())
    if market:
        select = select.filter_by(market=market)
    if without_image:
        select = select.filter_by(image=None)

    return db.session.execute(select).scalars()


def get_user(id):
    if id:
        return db.session.execute(db.select(User).filter_by(id=id)).scalar()


def get_ticker(id):
    if id:
        return db.session.execute(db.select(Ticker).filter_by(id=id)).scalar()


def get_tickers_count(market):
    return db.session.execute(db.select(func.count()).select_from(Ticker)
                              .filter_by(market=market)).scalar()


def get_users_count(type=None):
    select = db.select(func.count()).select_from(User)
    if type:
        select = select.filter_by(type=type)
    return db.session.execute(select).scalar()


def find_ticker_in_base(external_id, tickers, market, create=None):
    if external_id:
        ticker_id = add_prefix(external_id, market)

        for ticker in tickers:
            if ticker.id == ticker_id:
                return ticker

        if create:
            ticker = Ticker(id=ticker_id, market=market)
            db.session.add(ticker)
            tickers.append(ticker)
            return ticker


def load_image(url, market, ticker_id):
    upload_folder = current_app.config['UPLOAD_FOLDER']
    path = f'{upload_folder}/images/tickers/{market}'
    os.makedirs(path, exist_ok=True)

    ticker_id = remove_prefix(ticker_id, market)

    try:
        r = requests.get(url)
        original_img = Image.open(BytesIO(r.content))
        filename = f'{ticker_id}.{original_img.format}'.lower()
    except Exception:
        return None

    def resize_image(px):
        size = (px, px)
        path_local = os.path.join(path, str(px))
        os.makedirs(path_local, exist_ok=True)
        path_saved = os.path.join(path_local, filename)
        original_img.resize(size).save(path_saved)

    resize_image(24)
    resize_image(40)

    return filename
