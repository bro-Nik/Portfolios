import json

from flask import abort, render_template, session, url_for, request
from flask_login import login_required

from ..services import user_object_search_engine as ose
from ..app import db
from ..wraps import closed_for_demo_user
from ..general_functions import actions_on_objects
from ..portfolio.models import Ticker
from . import bp


@bp.route('/', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def assets():
    """Watchlist page and actions on assets."""
    market = request.args.get('market',
                              session.get('watchlist_market', 'crypto'))
    session['watchlist_market'] = market
    watchlist = ose.get_watchlist(market=market, **request.args) or abort(404)

    # Actions
    if request.method == 'POST':
        actions_on_objects(request.data, watchlist.service.get_asset)
        return ''

    return render_template('watchlist/assets.html', watchlist=watchlist,
                           market=market, status=request.args.get('status'))


@bp.route('/add_asset', methods=['POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_add():
    """ Add to Tracking list """
    asset = ose.get_watchlist_asset(create=True, **request.args) or abort(404)

    return str(url_for('.asset_info', ticker_id=asset.ticker_id,
                       only_content=request.args.get('only_content')))


@bp.route('/asset_info', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_info():
    """Asset page and actions on alerts."""
    asset = ose.get_watchlist_asset(create=True, **request.args) or abort(404)

    # Actions
    if request.method == 'POST':
        actions_on_objects(request.data, asset.service.get_alert)
        return ''

    return render_template('watchlist/asset_info.html', asset=asset)


@bp.route('/asset_settings', methods=['POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_settings():
    asset = ose.get_watchlist_asset(create=True, **request.args) or abort(404)

    # Apply settings
    asset.service.edit(request.form)
    return ''


@bp.route('/alert', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def alert_info():
    alert = ose.get_alert(create=True, **request.args) or abort(404)

    # Apply
    if request.method == 'POST':
        alert.asset_id = request.args.get('asset_id')
        alert.service.edit(request.form)
        return ''

    return render_template('watchlist/alert.html', asset=alert.asset,
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
