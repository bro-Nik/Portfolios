import json
from flask import render_template, session, url_for, request, Blueprint
from flask_login import login_required, current_user
from datetime import datetime

from portfolio_tracker.general_functions import get_price_list
from portfolio_tracker.models import Alert, Ticker, WatchlistAsset
from portfolio_tracker.wraps import demo_user_change
from portfolio_tracker.app import db


watchlist = Blueprint('watchlist',
                      __name__,
                      template_folder='templates',
                      static_folder='static')


def get_watchlist_asset(ticker_id, create=False):
    # if not current_user:
    # current_user = db.session.execute(db.select(User).filter_by(id=5)).scalar()
    if ticker_id:
        for asset in current_user.watchlist:
            if asset.ticker_id == ticker_id:
                return asset
        else:
            if create:
                asset = WatchlistAsset(ticker_id=ticker_id)
                current_user.watchlist.append(asset)
                db.session.commit()
                return asset
    return None


def get_alert(whitelist_asset, alert_id):
    if whitelist_asset and alert_id:
        for alert in whitelist_asset.alerts:
            if alert.id == int(alert_id):
                return alert
    return None


@watchlist.route('/', methods=['GET'])
@login_required
def assets():
    market = request.args.get('market')
    status = request.args.get('status')

    if market:
        session['watchlist_market'] = market
    else:
        market = session.get('watchlist_market', 'crypto')

    select = (db.select(WatchlistAsset).distinct()
        .filter_by(user_id=current_user.id))

    if status:
        select = select.join(WatchlistAsset.alerts).filter_by(status=status)

    select = select.join(WatchlistAsset.ticker).filter_by(market=market)
    tickers = db.session.execute(select).scalars()

    return render_template('watchlist/assets.html',
                           tickers=tuple(tickers),
                           status=status,
                           market=market)


@watchlist.route('/action', methods=['POST'])
@login_required
@demo_user_change
def assets_action():
    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data['action']

    for ticker_id in ids:
        watchlist_asset = get_watchlist_asset(ticker_id)

        if not watchlist_asset:
            continue

        if action == 'delete_with_orders':
            watchlist_asset.delete()

        elif action == 'delete':
            for alert in watchlist_asset.alerts:
                if not alert.transaction_id:
                    alert.delete()
            if watchlist_asset.is_empty():
                watchlist_asset.delete()

    db.session.commit()
    return ''


@watchlist.route('/add_asset', methods=['GET'])
@login_required
@demo_user_change
def asset_add():
    """ Add to Tracking list """
    watchlist_asset = get_watchlist_asset(request.args.get('ticker_id'), True)
    if not watchlist_asset:
        return ''

    return str(url_for('.asset_info',
                        ticker_id=watchlist_asset.ticker_id,
                        only_content=request.args.get('only_content')))


@watchlist.route('/watchlist_asset_update', methods=['POST'])
@login_required
@demo_user_change
def watchlist_asset_update():
    watchlist_asset = get_watchlist_asset(request.args.get('ticker_id'), True)
    if watchlist_asset:
        comment = request.form.get('comment')
        if comment is not None:
            watchlist_asset.comment = comment
        db.session.commit()
    return ''


@watchlist.route('/asset_info', methods=['GET'])
@login_required
def asset_info():
    # Если из портфеля, то не создавать, пока нет уведомлений
    need_create = not request.args.get('asset_id')

    ticker_id = request.args.get('ticker_id')
    watchlist_asset = get_watchlist_asset(ticker_id, need_create)
    if not watchlist_asset:
        watchlist_asset = WatchlistAsset()
        ticker = db.session.execute(db.select(Ticker)
                                    .filter_by(id=ticker_id)).scalar()
        watchlist_asset.ticker = ticker

    watchlist_asset.update_price()

    return render_template('watchlist/asset_info.html',
                           watchlist_asset=watchlist_asset)


@watchlist.route('/alerts_action', methods=['POST'])
@login_required
@demo_user_change
def alerts_action():
    watchlist_asset = get_watchlist_asset(request.args.get('ticker_id'))

    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data.get('action')

    for id in ids:
        alert = get_alert(watchlist_asset, id)
        if not alert:
            continue

        # Delete
        if action == 'delete':
            if not alert.transaction_id:
                alert.delete()

        # Convert to transaction
        elif action == 'convert_to_transaction':
            if alert.transaction:
                alert.transaction.convert_order_to_transaction()

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


@watchlist.route('/alert', methods=['GET'])
@login_required
def alert():
    watchlist_asset = get_watchlist_asset(request.args.get('ticker_id'))
    if not watchlist_asset:
        return ''

    watchlist_asset.update_price()
    alert = get_alert(watchlist_asset, request.args.get('alert_id'))

    return render_template('watchlist/alert.html',
                           watchlist_asset=watchlist_asset,
                           asset_id=request.args.get('asset_id'),
                           alert=alert)


@watchlist.route('/alert_update', methods=['POST'])
@login_required
@demo_user_change
def alert_update():
    """ Add or change alert """
    watchlist_asset = get_watchlist_asset(request.args.get('ticker_id'), True)
    if not watchlist_asset:
        return ''

    alert = get_alert(watchlist_asset, request.args.get('alert_id'))
    if not alert:
        alert = Alert(date=datetime.now().date(),
                      asset_id=request.args.get('asset_id'))
        watchlist_asset.alerts.append(alert)

    price_list = get_price_list()
    alert.price = float(request.form['price'])
    alert.price_ticker_id = request.form['price_ticker_id']
    alert.price_usd = alert.price / price_list.get(alert.price_ticker_id, 1)
    alert.comment = request.form['comment']

    asset_price = price_list.get(watchlist_asset.ticker_id, 1)
    alert.type = 'down' if asset_price >= alert.price_usd else 'up'

    db.session.commit()
    return ''


@watchlist.route('/ajax_stable', methods=['GET'])
@login_required
def ajax_stable_assets():
    result = []
    price_list = get_price_list()
    tickers = db.session.execute(db.select(Ticker).filter_by(stable=True)).scalars()

    asset_price = price_list.get(request.args['ticker_id'], 0)

    for ticker in tickers:
        result.append({'value': ticker.id,
                       'text': ticker.symbol.upper(),
                       'info': price_list.get(ticker.id, 1) * asset_price}) 

    if not result:
        result = {'message': 'Нет тикеров'}

    return json.dumps(result)
