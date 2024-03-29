import json

from flask import abort, render_template, session, url_for, request
from flask_login import login_required, current_user

from ..wraps import demo_user_change
from ..general_functions import actions_in
from ..portfolio.utils import get_ticker
from .utils import create_alert, create_watchlist_asset, get_alert, get_asset
from .models import db, WatchlistAsset
from . import bp


@bp.route('/', methods=['GET', 'POST'])
@login_required
@demo_user_change
def assets():
    """Watchlist page and actions on assets."""
    # Actions
    if request.method == 'POST':
        actions_in(request.data, get_asset)
        db.session.commit()
        return ''

    market = request.args.get('market',
                              session.get('watchlist_market', 'crypto'))
    session['watchlist_market'] = market
    status = request.args.get('status')

    select = (db.select(WatchlistAsset).distinct()
              .filter_by(user_id=current_user.id)
              .join(WatchlistAsset.ticker).filter_by(market=market))

    if status:
        select = select.join(WatchlistAsset.alerts).filter_by(status=status)

    assets = tuple(db.session.execute(select).scalars())

    return render_template('watchlist/assets.html', assets=assets,
                           status=status, market=market)


@bp.route('/add_asset', methods=['GET'])
@login_required
@demo_user_change
def asset_add():
    """ Add to Tracking list """
    ticker_id = request.args.get('ticker_id')
    asset = get_asset(ticker_id=ticker_id)
    if not asset:
        ticker = get_ticker(ticker_id) or abort(404)
        asset = create_watchlist_asset(ticker)
        db.session.commit()

    return str(url_for('.asset_info', ticker_id=asset.ticker_id,
                       only_content=request.args.get('only_content')))


@bp.route('/asset_info', methods=['GET', 'POST'])
@login_required
@demo_user_change
def asset_info():
    """Asset page and actions on alerts."""
    ticker_id = request.args.get('ticker_id')
    asset = get_asset(ticker_id=ticker_id)
    if not asset:
        ticker = get_ticker(ticker_id) or abort(404)
        asset = create_watchlist_asset(ticker)

    # Actions
    if request.method == 'POST':
        actions_in(request.data, get_alert, asset=asset)
        db.session.commit()
        return ''

    # Если из портфеля, то не создавать, пока нет уведомлений
    # need_create = not request.args.get('asset_id')
    # if need_create:
    #     db.session.commit()

    return render_template('watchlist/asset_info.html', asset=asset)


@bp.route('/asset_settings', methods=['POST'])
@login_required
@demo_user_change
def asset_settings():
    asset = get_asset(ticker_id=request.args.get('ticker_id')) or abort(404)

    # Apply settings
    asset.edit(request.form)
    db.session.commit()
    return ''


@bp.route('/alert', methods=['GET', 'POST'])
@login_required
@demo_user_change
def alert_info():
    ticker_id = request.args.get('ticker_id')
    asset = get_asset(ticker_id=ticker_id)
    if not asset:
        ticker = get_ticker(ticker_id) or abort(404)
        asset = create_watchlist_asset(ticker)
    alert = get_alert(request.args.get('alert_id'), asset
                      ) or create_alert(asset)

    # Apply
    if request.method == 'POST':
        alert.asset_id = request.args.get('asset_id')
        alert.edit(request.form)
        db.session.commit()
        return ''

    return render_template('watchlist/alert.html', asset=asset,
                           asset_id=request.args.get('asset_id'), alert=alert)


@bp.route('/ajax_stable', methods=['GET'])
@login_required
def ajax_stable_assets():
    from ..portfolio.models import Ticker

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
