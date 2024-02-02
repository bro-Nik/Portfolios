import json

from flask import abort, render_template, session, url_for, request
from flask_login import login_required, current_user

from portfolio_tracker.general_functions import actions_in

from ..wraps import demo_user_change
from .. import portfolio
from .utils import create_new_alert, create_new_asset, get_alert, get_asset
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
    actions_in(request.data, get_asset)
    return ''


@bp.route('/add_asset', methods=['GET'])
@login_required
@demo_user_change
def asset_add():
    """ Add to Tracking list """
    ticker = portfolio.utils.get_ticker(request.args.get('ticker_id')
                                        ) or abort(404)
    asset = get_asset(None, ticker.id)
    if not asset:
        asset = create_new_asset(ticker)
        db.session.commit()

    return str(url_for('.asset_info',
                       only_content=request.args.get('only_content'),
                       ticker_id=asset.ticker_id))


@bp.route('/watchlist_asset_update', methods=['POST'])
@login_required
@demo_user_change
def watchlist_asset_update():
    ticker = portfolio.utils.get_ticker(request.args.get('ticker_id')
                                        ) or abort(404)
    asset = get_asset(None, ticker.id) or create_new_asset(ticker)
    asset.edit(request.form)
    return ''


@bp.route('/asset_info', methods=['GET'])
@login_required
def asset_info():
    ticker = portfolio.utils.get_ticker(request.args.get('ticker_id')
                                        ) or abort(404)
    asset = get_asset(None, ticker.id) or create_new_asset(ticker)

    # Если из портфеля, то не создавать, пока нет уведомлений
    # need_create = not request.args.get('asset_id')
    # if need_create:
    #     db.session.commit()

    asset.price = asset.ticker.price

    return render_template('watchlist/asset_info.html', watchlist_asset=asset)


@bp.route('/alerts_action', methods=['POST'])
@login_required
@demo_user_change
def alerts_action():
    asset = get_asset(None, request.args.get('ticker_id')) or abort(404)
    actions_in(request.data, get_alert, asset=asset)
    return ''


@bp.route('/alert', methods=['GET'])
@login_required
def alert_info():
    ticker = portfolio.utils.get_ticker(request.args.get('ticker_id')
                                        ) or abort(404)
    asset = get_asset(None, ticker.id) or create_new_asset(ticker)
    alert = get_alert(request.args.get('alert_id'), asset)

    return render_template('watchlist/alert.html',
                           watchlist_asset=asset,
                           asset_id=request.args.get('asset_id'),
                           alert=alert)


@bp.route('/alert_update', methods=['POST'])
@login_required
@demo_user_change
def alert_update():
    """ Add or change alert """
    ticker = portfolio.utils.get_ticker(request.args.get('ticker_id')
                                        ) or abort(404)
    asset = get_asset(None, ticker.id) or create_new_asset(ticker)
    alert = get_alert(request.args.get('alert_id'), asset
                      ) or create_new_alert(asset)

    alert.asset_id = request.args.get('asset_id')
    alert.edit(request.form)
    return ''


@bp.route('/ajax_stable', methods=['GET'])
@login_required
def ajax_stable_assets():

    result = []
    stables = db.session.execute(
        db.select(portfolio.models.Ticker).filter_by(stable=True)).scalars()

    ticker = db.session.execute(
        db.select(portfolio.models.Ticker)
        .filter_by(id=request.args['ticker_id'])).scalar()
    asset_price = ticker.price

    for stable in stables:
        result.append({'value': stable.id,
                       'text': stable.symbol.upper(),
                       'info': stable.price * asset_price})

    if not result:
        result = {'message': 'Нет тикеров'}

    return json.dumps(result)
