import json
from flask import flash, render_template, redirect, url_for, request, Blueprint
from flask_login import login_required, current_user
from datetime import datetime

from portfolio_tracker.general_functions import float_or_other, get_ticker, \
    get_price_list
from portfolio_tracker.models import Alert, Ticker, WhitelistTicker
from portfolio_tracker.wraps import demo_user_change
from portfolio_tracker.app import db


whitelist = Blueprint('whitelist',
                      __name__,
                      template_folder='templates',
                      static_folder='static')


def get_whitelist_ticker(ticker_id, can_new=False):
    ticker = db.session.execute(
        db.select(WhitelistTicker).filter_by(user_id=current_user.id,
                                             ticker_id=ticker_id)).scalar()
    if not ticker and can_new:
        ticker = WhitelistTicker(user_id=current_user.id, ticker_id=ticker_id)
        db.session.add(ticker)
        db.session.commit()

    return ticker


def get_user_alert(id):
    if id:
        alert = db.session.execute(db.select(Alert).filter_by(id=id)).scalar()
        if alert and alert.whitelist_ticker.user_id == current_user.id:
            return alert
    return None


@whitelist.route('/<string:market_id>', methods=['GET'])
@whitelist.route('', methods=['GET'])
@login_required
@demo_user_change
def tickers(market_id=None):
    market_id = market_id if market_id else 'crypto'
    status = request.args.get('status')

    select = (db.select(WhitelistTicker).distinct()
        .filter_by(user_id=current_user.id))

    if status:
        select = (select.join(WhitelistTicker.alerts)
            .filter(Alert.status == status))

    select = (select.join(WhitelistTicker.ticker)
        .where(Ticker.market_id == market_id))
    
    tickers = db.session.execute(select).scalars()

    return render_template('whitelist/tickers.html',
                           tickers=tuple(tickers),
                           status=status,
                           market_id=market_id)


@whitelist.route('/action', methods=['POST'])
@login_required
@demo_user_change
def tickers_action():
    data = json.loads(request.data) if request.data else {}

    ids = data.get('ids')
    for id in ids:
        whitelist_ticker = get_whitelist_ticker(id)

        if not whitelist_ticker:
            continue

        # удаляем уведомления
        for alert in whitelist_ticker.alerts:
            db.session.delete(alert)

        db.session.delete(whitelist_ticker)

    db.session.commit()
    return ''


@whitelist.route('/add_ticker', methods=['GET'])
@login_required
@demo_user_change
def add_ticker():
    """ Add to Tracking list """
    ticker_id = request.args.get('ticker_id')
    whitelist_ticker = get_whitelist_ticker(ticker_id, True)
    return redirect(url_for('.ticker_info',
                            market_id=whitelist_ticker.ticker.market_id,
                            ticker_id=whitelist_ticker.ticker_id,
                            only_content=request.args.get('only_content')))


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
    return ''


@whitelist.route('/<string:market_id>/ticker_<string:ticker_id>')
@login_required
@demo_user_change
def ticker_info(market_id, ticker_id):
    price_list = get_price_list(market_id)
    price = float_or_other(price_list.get(ticker_id), 0)

    whitelist_ticker = get_whitelist_ticker(ticker_id)

    # не добавляем если пока нет уведомлений
    ticker = {}
    if not whitelist_ticker:
        ticker = get_ticker(ticker_id)
    return render_template('whitelist/ticker_info.html',
                           whitelist_ticker=whitelist_ticker,
                           ticker=ticker,
                           market_id=market_id,
                           price=price)


@whitelist.route('/alerts_action', methods=['POST'])
@login_required
@demo_user_change
def alerts_action():
    data = json.loads(request.data) if request.data else {}
    ids = data.get('ids')
    action = data.get('action')

    for id in ids:
        alert = get_user_alert(id)
        if not alert:
            continue

        # Delete
        if action == 'delete':
            if not alert.transaction_id:
                db.session.delete(alert)

        # Convert to transaction
        elif action == 'convert_to_transaction':
            alert.transaction.order = 0
            alert.transaction.date = datetime.now().date()
            alert.status = 'off'

        # Turn off
        elif action == 'turn_off':
            if not alert.transaction_id:
                alert.status = 'off'

        # Turn on
        elif action == 'turn_on':
            if alert.transaction_id and alert.status != 'on':
                alert.transaction_id = None
                alert.asset_id = None
            alert.status = 'on'

    db.session.commit()
    return ''


@whitelist.route('/<string:market_id>/whitelist_ticker/alert', methods=['GET'])
@login_required
@demo_user_change
def alert(market_id):
    whitelist_ticker_id = request.args.get('whitelist_ticker_id')
    ticker_id = request.args.get('ticker_id')
    alert = get_user_alert(request.args.get('alert_id'))

    price_list = get_price_list(market_id)
    price = float_or_other(price_list.get(ticker_id), 0)

    return render_template('whitelist/alert.html',
                           whitelist_ticker_id=whitelist_ticker_id,
                           ticker_id=ticker_id,
                           alert=alert,
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
    return ''
