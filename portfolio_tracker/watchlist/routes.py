import json

from flask import abort, render_template, session, url_for, request
from flask_login import login_required

from ..app import db
from ..wraps import closed_for_demo_user
from ..general_functions import actions_in
from ..portfolio.models import Ticker
from .models import Watchlist
from . import bp


@bp.route('/', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def assets():
    """Watchlist page and actions on assets."""
    market = request.args.get('market',
                              session.get('watchlist_market', 'crypto'))
    session['watchlist_market'] = market
    status = request.args.get('status')
    watchlist = Watchlist.get(market, status)

    # Actions
    if request.method == 'POST':
        actions_in(request.data, watchlist.get_asset)
        db.session.commit()
        return ''

    return render_template('watchlist/assets.html', watchlist=watchlist,
                           market=market, status=status)


@bp.route('/add_asset', methods=['POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_add():
    """ Add to Tracking list """
    watchlist = Watchlist.get()
    ticker_id = request.args.get('ticker_id')
    asset = watchlist.get_asset(ticker_id)
    if not asset:
        ticker = Ticker.get(ticker_id) or abort(404)
        asset = watchlist.create_asset(ticker)

    return str(url_for('.asset_info', ticker_id=asset.ticker_id,
                       only_content=request.args.get('only_content')))


@bp.route('/asset_info', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_info():
    """Asset page and actions on alerts."""
    watchlist = Watchlist.get()
    ticker_id = request.args.get('ticker_id')
    asset = watchlist.get_asset(ticker_id)
    if not asset:
        ticker = Ticker.get(ticker_id) or abort(404)
        asset = watchlist.create_asset(ticker)

        # Если из портфеля, то не создавать, пока нет уведомлений
        need_create = not request.args.get('asset_id')
        if need_create:
            watchlist.assets.append(asset)
            db.session.commit()

    # Actions
    if request.method == 'POST':
        actions_in(request.data, asset.get_alert)
        db.session.commit()
        return ''

    return render_template('watchlist/asset_info.html', asset=asset)


@bp.route('/asset_settings', methods=['POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_settings():
    watchlist = Watchlist.get()
    asset = watchlist.get_asset(request.args.get('ticker_id')) or abort(404)

    # Apply settings
    asset.edit(request.form)
    db.session.commit()
    return ''


@bp.route('/alert', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def alert_info():
    watchlist = Watchlist.get()
    ticker_id = request.args.get('ticker_id')
    asset = watchlist.get_asset(ticker_id)
    if not asset:
        ticker = Ticker.get(ticker_id) or abort(404)
        asset = watchlist.create_asset(ticker)

    alert = asset.get_alert(request.args.get('alert_id')
                            ) or asset.create_alert()

    # Apply
    if request.method == 'POST':
        if asset not in watchlist.assets:
            watchlist.assets.append(asset)
        if alert not in asset.alerts:
            asset.alerts.append(alert)

        alert.asset_id = request.args.get('asset_id')
        alert.edit(request.form)
        db.session.commit()
        return ''

    return render_template('watchlist/alert.html', asset=asset,
                           asset_id=request.args.get('asset_id'), alert=alert)


@bp.route('/ajax_stable', methods=['GET'])
@login_required
def ajax_stable_assets():
    result = []
    stables = db.session.execute(
        db.select(Ticker).filter_by(stable=True)).scalars()

    ticker = db.session.execute(
        db.select(Ticker)
        .filter_by(id=request.args['ticker_id'])).scalar()
    asset_price = ticker.price

    for stable in stables:
        result.append({'value': stable.id,
                       'text': stable.symbol.upper(),
                       'info': stable.price * asset_price})

    if not result:
        result = {'message': 'Нет тикеров'}

    return json.dumps(result)
