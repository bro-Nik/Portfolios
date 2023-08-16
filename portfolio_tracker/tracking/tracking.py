from flask import flash, render_template, redirect, url_for, request, Blueprint
from flask_login import login_required, current_user
from portfolio_tracker.models import Trackedticker
from portfolio_tracker.wraps import demo_user_change

from portfolio_tracker.app import db


tracking = Blueprint('tracking', __name__, template_folder='templates', static_folder='static')


def get_user_tracked_tickers(market_id):
    # return db.session.execute(
    #     db.select(Trackedticker).filter_by(user_id=current_user.id)).scalars()
    return db.session.execute(
        db.select(Trackedticker).filter_by(user_id=current_user.id)
    .join(Trackedticker.ticker).filter_by(market_id=market_id)).scalars()


@tracking.route('/<string:market_id>', methods=['GET'])
@login_required
def tracking_list(market_id):
    """ Tracking list page """
    tracked_tickers = get_user_tracked_tickers(market_id)

    # для запрета удаления тикера, если есть ордер
    orders = []
    markets = []
    for ticker in tracked_tickers:
        for alert in ticker.alerts:
            if alert.comment == 'Ордер':
                orders.append(ticker.ticker_id)

    return render_template('tracking/tracking_list.html',
                           tracked_tickers=tuple(tracked_tickers),
                           market_id=market_id,
                           orders=orders)
