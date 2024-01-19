import json

from flask import render_template, session, url_for, request
from flask_login import login_required, current_user

from ..wraps import demo_user_change
from ..portfolio import models as portfolio
from .utils import actions_on_alerts, actions_on_watchlist, create_new_alert, \
    get_alert, get_watchlist_asset
from .models import db, WatchlistAsset
from . import bp


@bp.route('/', methods=['GET'])
@login_required
def assets():
    market = request.args.get('market')
    status = request.args.get('status')

    if market:
        session['watchlist_market'] = market
    else:
        market = session.get('watchlist_market', 'crypto')

    select = (db.select(WatchlistAsset).distinct()
              .filter_by(user_id=current_user.id)
              .join(WatchlistAsset.ticker).filter_by(market=market))

    if status:
        select = select.join(WatchlistAsset.alerts).filter_by(status=status)

    tickers = tuple(db.session.execute(select).scalars())

    return render_template('watchlist/assets.html', tickers=tickers,
                           status=status, market=market)


@bp.route('/action', methods=['POST'])
@login_required
@demo_user_change
def assets_action():
    data = json.loads(request.data) if request.data else {}

    actions_on_watchlist(data['ids'], data['action'])
    return ''


@bp.route('/add_asset', methods=['GET'])
@login_required
@demo_user_change
def asset_add():
    """ Add to Tracking list """
    asset = get_watchlist_asset(request.args.get('ticker_id'), create=True)

    return str(url_for('.asset_info',
                       only_content=request.args.get('only_content'),
                       ticker_id=asset.ticker_id)) if asset else ''


@bp.route('/watchlist_asset_update', methods=['POST'])
@login_required
@demo_user_change
def watchlist_asset_update():
    asset = get_watchlist_asset(request.args.get('ticker_id'), True)
    if asset:
        asset.edit(request.form)
    return ''


@bp.route('/asset_info', methods=['GET'])
@login_required
def asset_info():
    # Если из портфеля, то не создавать, пока нет уведомлений
    need_create = not request.args.get('asset_id')

    ticker_id = request.args.get('ticker_id')
    asset = get_watchlist_asset(ticker_id, need_create)
    if not asset:
        ticker = db.session.execute(db.select(portfolio.Ticker)
                                    .filter_by(id=ticker_id)).scalar()
        asset = WatchlistAsset(ticker=ticker)

    asset.price = asset.ticker.price

    return render_template('watchlist/asset_info.html', watchlist_asset=asset)


@bp.route('/alerts_action', methods=['POST'])
@login_required
@demo_user_change
def alerts_action():
    watchlist_asset = get_watchlist_asset(request.args.get('ticker_id'))
    data = json.loads(request.data) if request.data else {}

    actions_on_alerts(watchlist_asset, data['ids'], data['action'])
    return ''


@bp.route('/alert', methods=['GET'])
@login_required
def alert_info():
    ticker_id = request.args.get('ticker_id')
    if not ticker_id:
        return ''

    watchlist_asset = get_watchlist_asset(ticker_id, True)
    alert = get_alert(watchlist_asset, request.args.get('alert_id'))

    return render_template('watchlist/alert.html',
                           watchlist_asset=watchlist_asset,
                           asset_id=request.args.get('asset_id'),
                           alert=alert)


@bp.route('/alert_update', methods=['POST'])
@login_required
@demo_user_change
def alert_update():
    """ Add or change alert """
    watchlist_asset = get_watchlist_asset(request.args.get('ticker_id'), True)
    if not watchlist_asset:
        return ''

    alert = get_alert(watchlist_asset, request.args.get('alert_id'))
    if not alert:
        alert = create_new_alert(watchlist_asset)

    alert.asset_id = request.args.get('asset_id')
    alert.edit(request.form)

    db.session.commit()
    return ''


@bp.route('/ajax_stable', methods=['GET'])
@login_required
def ajax_stable_assets():

    result = []
    stables = db.session.execute(
        db.select(portfolio.Ticker).filter_by(stable=True)).scalars()

    ticker = db.session.execute(
        db.select(portfolio.Ticker)
        .filter_by(id=request.args['ticker_id'])).scalar()
    asset_price = ticker.price

    for stable in stables:
        result.append({'value': stable.id,
                       'text': stable.symbol.upper(),
                       'info': stable.price * asset_price})

    if not result:
        result = {'message': 'Нет тикеров'}

    return json.dumps(result)
