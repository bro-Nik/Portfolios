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
from ..general_functions import add_prefix, redis_decode, remove_prefix
from ..portfolio.models import Ticker
from ..user.models import User


Market: TypeAlias = Literal['crypto', 'stocks', 'currency']


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


def get_tickers(market: str | None = None,
                without_image: bool = False) -> list[Ticker]:
    select = db.select(Ticker).order_by(Ticker.market_cap_rank.is_(None),
                                        Ticker.market_cap_rank.asc())
    if market:
        select = select.filter_by(market=market)
    if without_image:
        select = select.filter_by(image=None)

    return list(db.session.execute(select).scalars())


def get_all_users() -> tuple[User, ...]:
    return tuple(db.session.execute(db.select(User)).scalars())


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
