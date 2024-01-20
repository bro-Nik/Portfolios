import os
from datetime import datetime, timezone
import pickle
from typing import Literal, TypeAlias
from io import BytesIO
import requests

from flask import current_app
from sqlalchemy import func
from PIL import Image

from ..app import db, redis
from ..general_functions import redis_decode
from ..portfolio.models import Ticker
from ..user.models import User


Market: TypeAlias = Literal['crypto', 'stocks', 'currency']


def get_prefix(market: Market) -> str:
    return current_app.config[f'{market.upper()}_PREFIX']


def task_log_name(market: Market) -> str:
    return f"task-log-{market}"


def get_task_log(market: Market) -> list:
    key = task_log_name(market)
    return redis_decode(key, default=[])


def task_log(text: str, market: Market) -> None:
    key = task_log_name(market)
    log = get_task_log(market)
    log.append({'text': text, 'time': datetime.now(timezone.utc)})
    redis.set(key, pickle.dumps(log))


def remove_prefix(ticker_id: str, market: Market) -> str:
    prefix = get_prefix(market)
    if ticker_id.startswith(prefix):
        ticker_id = ticker_id[len(prefix):]

    return ticker_id


def add_prefix(ticker_id: str, market: Market) -> str:
    return (get_prefix(market) + ticker_id).lower()


def get_tickers(market: str | None = None,
                without_image: bool = False) -> list[Ticker]:
    select = db.select(Ticker).order_by(Ticker.market_cap_rank.is_(None),
                                        Ticker.market_cap_rank.asc())
    if market:
        select = select.filter_by(market=market)
    if without_image:
        select = select.filter_by(image=None)

    return list(db.session.execute(select).scalars())


def get_user(user_id: int | str | None) -> User | None:
    if user_id:
        return db.session.execute(
            db.select(User).filter_by(id=user_id)).scalar()


def get_all_users() -> tuple[User, ...]:
    return tuple(db.session.execute(db.select(User)).scalars())


def get_ticker(ticker_id: str | None) -> Ticker | None:
    if ticker_id:
        return db.session.execute(
            db.select(Ticker).filter_by(id=ticker_id)).scalar()


def get_tickers_count(market: Market) -> int | None:
    return db.session.execute(db.select(func.count()).select_from(Ticker)
                              .filter_by(market=market)).scalar()


def get_users_count(user_type: str | None = None) -> int | None:
    select = db.select(func.count()).select_from(User)
    if user_type:
        select = select.filter_by(type=user_type)
    return db.session.execute(select).scalar()


def find_ticker_in_base(external_id: str, tickers: list[Ticker],
                        market: Market, create: bool = False) -> Ticker | None:
    if external_id:
        ticker_id = add_prefix(external_id, market)

        for ticker in tickers:
            if ticker.id == ticker_id:
                return ticker

        if create:
            ticker = Ticker()
            ticker.id = ticker_id
            ticker.market = market
            db.session.add(ticker)
            tickers.append(ticker)
            return ticker


def request(url: str, market: Market) -> requests.models.Response | None:
    try:
        response = requests.get(url)
        if response.status_code == 200:
            task_log('Удачный запрос', market)
            current_app.logger.info('Удачный запрос')
            return response

        task_log(f'Ошибка, Код ответа: {response.status_code}', market)
        current_app.logger.warning('Ошибка', exc_info=True)

    except requests.exceptions.ConnectionError as e:
        task_log(f'Ошибка: {type(e)}', market)
        current_app.logger.warning('Ошибка', exc_info=True)

    except Exception as e:
        task_log(f'Ошибка: {type(e)}', market)
        current_app.logger.error('Ошибка', exc_info=True)
        raise


def request_json(url: str, market: Market) -> dict | None:
    data = request(url, market)
    if data:
        return data.json()


def load_image(url: str, market: Market, ticker_id: str) -> str | None:
    task_log('Загрузка иконки - Старт', market)

    upload_folder = current_app.config['UPLOAD_FOLDER']
    path = f'{upload_folder}/images/tickers/{market}'
    os.makedirs(path, exist_ok=True)

    ticker_id = remove_prefix(ticker_id, market)

    r = request(url, market)
    if not r:
        return None

    try:
        original_img = Image.open(BytesIO(r.content))
        filename = f'{ticker_id}.{original_img.format}'.lower()
    except Exception as e:
        task_log(f'Ошибка: {type(e)}', market)
        current_app.logger.error('Ошибка', exc_info=True)
        raise

    def resize_image(px):
        size = (px, px)
        path_local = os.path.join(path, str(px))
        os.makedirs(path_local, exist_ok=True)
        path_saved = os.path.join(path_local, filename)
        original_img.resize(size).save(path_saved)

    resize_image(24)
    resize_image(40)

    task_log('Загрузка иконки - Конец', market)

    return filename


def actions_on_users(ids: list[int | str | None], action: str) -> None:
    for user_id in ids:
        user = get_user(user_id)
        if not user:
            continue

        if action == 'user_to_admin':
            user.make_admin()

        elif action == 'admin_to_user':
            user.unmake_admin()

        elif action == 'delete':
            user.delete()

        db.session.commit()


def actions_on_tickers(ids: list[str | None], action: str) -> None:
    for ticker_id in ids:
        ticker = get_ticker(ticker_id)
        if not ticker:
            continue

        if action == 'delete':
            ticker.delete()

    db.session.commit()
