from __future__ import annotations
import os
from typing import TYPE_CHECKING, List
from io import BytesIO

from flask import current_app
from sqlalchemy import func
from PIL import Image

from portfolio_tracker.app import db, celery
from portfolio_tracker.general_functions import MARKETS, Market, add_prefix, remove_prefix
from portfolio_tracker.portfolio.models import Ticker
from portfolio_tracker.watchlist.models import WatchlistAsset
from portfolio_tracker.user.models import User
from portfolio_tracker.admin.services.integrations_api import API_NAMES, ApiIntegration, request_data
from portfolio_tracker.admin.services.integrations_market import MarketIntegration
from portfolio_tracker.admin.services.integrations_other import MODULE_NAMES, OtherIntegration

if TYPE_CHECKING:
    pass


def get_tickers(market: Market | None = None, without_image: bool = False,
                without_ids: List[str] | None = None) -> List[Ticker]:
    select = db.select(Ticker).order_by(Ticker.market_cap_rank.is_(None),
                                        Ticker.market_cap_rank.asc())
    if market:
        select = select.filter_by(market=market)
    if without_image:
        select = select.filter_by(image=None)
    if without_ids:
        select = select.filter(Ticker.id.notin_(without_ids))

    return list(db.session.execute(select).scalars())


def get_tickers_count(market: Market) -> int:
    return db.session.execute(db.select(func.count()).select_from(Ticker)
                              .filter_by(market=market)).scalar() or 0


def get_users_count(user_type: str | None = None) -> int:
    select = db.select(func.count()).select_from(User)
    if user_type:
        select = select.filter_by(type=user_type)
    return db.session.execute(select).scalar() or 0


def find_ticker_in_list(external_id: str, tickers: list[Ticker],
                        market: Market) -> Ticker | None:
    ticker_id = add_prefix(external_id, market)

    for ticker in tickers:
        if ticker.id == ticker_id:
            return ticker


def create_ticker(external_id: str, market: Market) -> Ticker:
    ticker_id = add_prefix(external_id, market)

    ticker = Ticker()
    ticker.id = ticker_id
    ticker.market = market
    db.session.add(ticker)
    return ticker


def load_image(url: str, market: Market, ticker_id: str, api: ApiIntegration
               ) -> str | None:

    # Папка хранения изображений
    upload_folder = current_app.config['UPLOAD_FOLDER']
    path = f'{upload_folder}/images/tickers/{market}'
    os.makedirs(path, exist_ok=True)

    ticker_id = remove_prefix(ticker_id, market)

    response = request_data(api, url)
    if not response:
        return

    try:
        original_img = Image.open(BytesIO(response.content))
        filename = f'{ticker_id}.{original_img.format}'.lower()
        api.logs.set('info', f'Загружена иконка ## {ticker_id}')
    except Exception as e:
        api.logs.set('error', f'Ошибка загрузки иконки: {type(e)}')
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

    return filename


def get_tasks() -> list:
    i = celery.control.inspect()
    active = i.active()
    scheduled = i.scheduled()
    registered = i.registered()

    tasks_list = []
    tasks_names = []
    if active:
        for server in active:
            for task in active[server]:
                tasks_list.append({'name': task['name'], 'id': task['id']})
                tasks_names.append(task['name'])

    if scheduled:
        for server in scheduled:
            for task in scheduled[server]:
                if task['request']['name'] not in tasks_names:
                    tasks_list.append({'name': task['request']['name'],
                                       'id': task['request']['id']})
                    tasks_names.append(task['request']['name'])

    if registered:
        for server in registered:
            for task in registered[server]:
                if task not in tasks_names:
                    tasks_list.append({'name': task})

    return tasks_list


def task_action(active_ids: list, action: str, task_id: str | None = None,
                task_name: str | None = None) -> None:
    if action == 'stop' and task_id in active_ids:
        celery.control.revoke(task_id, terminate=True)
    elif action == 'start' and task_id not in active_ids:
        task = celery.signature(task_name)
        task.delay()


def alerts_update(market):
    # Отслеживаемые тикеры
    tracked_tickers = db.session.execute(
        db.select(WatchlistAsset)
        .join(WatchlistAsset.ticker).filter_by(market=market)).scalars()

    for ticker in tracked_tickers:
        price = ticker.ticker.price
        # ToDo Перенести в запрос
        if not ticker.alerts or not price:
            continue

        for alert in ticker.alerts:
            if alert.status != 'on':
                continue

            if ((alert.type == 'down' and price <= alert.price)
                    or (alert.type == 'up' and price >= alert.price)):
                alert.status = 'worked'

    db.session.commit()


def get_module(module_name: str | None
               ) -> MarketIntegration | ApiIntegration | OtherIntegration | None:
    """Возвращает модуль, если находит среди списка имен.

    Keyword arguments:
    module_name -- the real part (default 0.0)

    """
    if module_name in MARKETS:
        return MarketIntegration(module_name)
    if module_name in API_NAMES:
        return ApiIntegration(module_name)
    if module_name in MODULE_NAMES:
        return OtherIntegration(module_name)
