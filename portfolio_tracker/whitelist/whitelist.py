import json
from flask import flash, render_template, redirect, url_for, request, Blueprint
from flask_login import login_required, current_user
from datetime import datetime

from portfolio_tracker.general_functions import dict_get_or_other, float_or_other, get_ticker, price_list_def
from portfolio_tracker.models import Alert, Asset, Portfolio, Ticker, WhitelistTicker
from portfolio_tracker.wraps import demo_user_change
from portfolio_tracker.app import db


whitelist = Blueprint('whitelist', __name__, template_folder='templates', static_folder='static')


def get_whitelist_ticker(ticker_id, can_new=False):
    ticker = db.session.execute(
        db.select(WhitelistTicker).filter_by(user_id=current_user.id,
                                             ticker_id=ticker_id)).scalar()
    if not ticker and can_new:
        ticker = WhitelistTicker(user_id=current_user.id, ticker_id=ticker_id)
        db.session.add(ticker)
        db.session.commit()

    return ticker


def get_whitelist_tickers(market_id):
    return db.session.execute(
        db.select(WhitelistTicker).filter_by(user_id=current_user.id)
        .join(WhitelistTicker.ticker)
        .where(Ticker.market_id == market_id)).scalars()
    # return db.session.execute(
    #     db.select(Ticker).filter(Ticker.market_id == market_id)
    #     .join(Ticker.alerts)
    #     .join(Alert.asset)
    #     .join(Asset.portfolio)
    #     .where(Portfolio.user_id == current_user.id)).scalars()


# def get_user_tracked_ticker(ticker_id):
#     return db.session.execute(
#         db.select(Ticker).filter_by(id=ticker_id)
#         .join(Ticker.alerts)
#         .join(Alert.asset)
#         .join(Asset.portfolio)
#         .where(Portfolio.user_id == current_user.id)).scalar()


def get_user_alert(id):
    return db.session.execute(db.select(Alert).filter_by(id=id)).scalar()


@whitelist.route('/<string:market_id>', methods=['GET'])
@login_required
def whitelist_tickers(market_id):
    """ Whitelist page """
    tickers = tuple(get_whitelist_tickers(market_id))
    orders = []

    return render_template('whitelist/whitelist.html',
                           tickers=tickers,
                           market_id=market_id,
                           orders=orders)


@whitelist.route('/ticker_<string:ticker_id>')
@login_required
def ticker_info(ticker_id):
    price_list = price_list_def()
    price = float_or_other(price_list.get(ticker_id), 0)

    whitelist_ticker = get_whitelist_ticker(ticker_id)

    # не добавляем если пока нет уведомлений
    ticker = {}
    if not whitelist_ticker:
        ticker = get_ticker(ticker_id)
    return render_template('whitelist/ticker_info.html',
                           whitelist_ticker=whitelist_ticker,
                           ticker=ticker,
                           price=price)


@whitelist.route('/whitelist_ticker/alert', methods=['GET'])
@login_required
def alert():
    whitelist_ticker_id = request.args.get('whitelist_ticker_id')
    ticker_id = request.args.get('ticker_id')

    price_list = price_list_def()
    price = float_or_other(price_list.get(ticker_id), 0)

    return render_template('whitelist/alert.html',
                           whitelist_ticker_id=whitelist_ticker_id,
                           ticker_id=ticker_id,
                           price=price)


@whitelist.route('/alert_update', methods=['POST'])
@login_required
@demo_user_change
def alert_update():
    """ Add or change alert """
    whitelist_ticker_id = request.args.get('whitelist_ticker_id')
    asset_id = request.args.get('asset_id')
    alert = get_user_alert(request.args.get('alert_id'))

    if not whitelist_ticker_id:
        ticker_id = request.args.get('ticker_id')
        whitelist_ticker = get_whitelist_ticker(ticker_id, True)
        whitelist_ticker_id = whitelist_ticker.id

    if not alert:
        alert = Alert(date=datetime.now().date(),
                      whitelist_ticker_id=whitelist_ticker_id,
                      asset_id=asset_id if asset_id else None)
        db.session.add(alert)

    alert.price = request.form['price']
    alert.type = request.form['type']
    alert.comment = request.form['comment']

    db.session.commit()

    # добавление уведомления в список
    # alerts_redis = redis.get('not_worked_alerts')
    # not_worked_alerts = pickle.loads(alerts_redis) if alerts_redis else {}
    # not_worked_alerts[alert.id] = {}
    # not_worked_alerts[alert.id]['type'] = alert.type
    # not_worked_alerts[alert.id]['price'] = alert.price
    # not_worked_alerts[alert.id]['ticker_id'] = ticker_id
    # redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))
    #
    return ''


@whitelist.route('/add_ticker', methods=['GET'])
@demo_user_change
def add_ticker():
    """ Add to Tracking list """
    ticker_id = request.args.get('ticker_id')
    whitelist_ticker = get_whitelist_ticker(ticker_id, True)
    load_only_content = request.args.get('load_only_content')
    return redirect(url_for('.ticker_info',
                            ticker_id=whitelist_ticker.ticker_id,
                            load_only_content=load_only_content))


@whitelist.route('/action', methods=['POST'])
@demo_user_change
def whitelist_action():
    data = json.loads(request.data) if request.data else {}

    ids = data.get('ids')
    for id in ids:
        whitelist_ticker = get_whitelist_ticker(id)

        if not whitelist_ticker:
            continue

        # удаляем уведомления
        if whitelist_ticker.alerts:
            # alerts_redis = redis.get('not_worked_alerts')
            #
            # not_worked_alerts = pickle.loads(
            #         alerts_redis) if alerts_redis else {}
            #
            # alerts_redis = redis.get('worked_alerts')
            # worked_alerts = pickle.loads(alerts_redis) if alerts_redis else {}
            #
            # for alert in worked_alerts[current_user.id]:
            #     if alert['name'] == whitelist_ticker.ticker.name:
            #         worked_alerts[current_user.id].remove(alert)

            for alert in whitelist_ticker.alerts:
                # not_worked_alerts.pop(alert.id, None)

                db.session.delete(alert)

            # redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))
            # redis.set('worked_alerts', pickle.dumps(worked_alerts))

        db.session.delete(whitelist_ticker)

    db.session.commit()

    return ''


@whitelist.route('/whitelist_ticker_update', methods=['POST'])
@login_required
@demo_user_change
def whitelist_ticker_update():
    ticker_id = request.args.get('ticker_id')
    whitelist_ticker = get_whitelist_ticker(ticker_id, True)

    comment = request.form.get('comment')
    if comment is not None:
        whitelist_ticker.comment = comment
    db.session.commit()
    return 'OK'


@whitelist.route('/alerts_action', methods=['POST'])
@login_required
@demo_user_change
def alerts_action():
    data = json.loads(request.data) if request.data else {}
    ids = data.get('ids')

    for id in ids:
        alert = get_user_alert(id)
        if not alert.order:
            db.session.delete(alert)

    db.session.commit()

    return ''

# def alert_delete_def(id=None):
#     alert_in_base = db.session.execute(
#             db.select(Alert).filter_by(id=id)).scalar()
    # update_alerts_redis(alert_in_base.id)
    # if alert_in_base:
    #     update_alerts_redis(alert_in_base.id)
    #     need_del_ticker = True
    #
    #     for alert in alert_in_base.trackedticker.alerts:
    #         if alert.id != alert_in_base.id:
    #             need_del_ticker = False
    #             break
    #
    #     if not alert_in_base.asset_id and need_del_ticker:
    #         session['last_url'] = session['last_url'].\
    #                     replace(('/'
    #                             + alert_in_base.trackedticker.ticker.market.id
    #                             + '/'
    #                             + alert_in_base.trackedticker.ticker_id), '')
    #     if need_del_ticker:
    #         db.session.delete(alert_in_base.trackedticker)
    #     db.session.delete(alert_in_base)
    #     db.session.commit()
