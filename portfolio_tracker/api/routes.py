import json
from datetime import datetime, timezone

from flask import request
from flask_babel import gettext
from flask_login import current_user, login_required


from ..app import db
from ..jinja_filters import currency_price, currency_quantity, smart_round
from ..general_functions import remove_prefix
from ..portfolio.models import Ticker
from ..wallet.models import Wallet
from . import bp


@bp.before_request
def before_request():
    if current_user.is_authenticated and current_user.info:
        current_user.info.last_visit = datetime.now(timezone.utc)
        db.session.commit()


@bp.route('/worked_alerts_count', methods=['GET'])
@login_required
def worked_alerts_count():
    count = 0
    for wasset in current_user.watchlist:
        for alert in wasset.alerts:
            if alert.status == 'worked':
                count += 1
    return f'<span>{count}</span>' if count else ''


@bp.route('/all_currencies', methods=['GET'])
@login_required
def all_currencies():
    market = 'currency'
    result = []

    # currencies = db.session.execute(
    #     db.select(Ticker).filter_by(market=market)).scalars()

    # ToDo
    ids = ['cu-usd', 'cu-rub', 'cu-eur', 'cu-jpy']
    currencies = db.session.execute(
        db.select(Ticker).filter(Ticker.id.in_(ids))).scalars()
    for currency in currencies:
        result.append({'value': remove_prefix(currency.id, market),
                       'text': currency.symbol.upper(),
                       'subtext': currency.name})
    return json.dumps(result, ensure_ascii=False)


@bp.route('/portfolios', methods=['GET'])
@login_required
def portfolios():
    result = []

    for portfolio in current_user.portfolios:

        result.append({'value': str(portfolio.id),
                       'text': portfolio.name})

    return json.dumps(result)


@bp.route('/wallets_to_sell', methods=['GET'])
@login_required
def wallets_to_sell():
    ticker_id = request.args['ticker_id']
    result = []

    for wallet in current_user.wallets:
        for asset in wallet.assets:
            if ticker_id != asset.ticker_id:
                continue

            if asset.free > 0:
                quantity = currency_quantity(asset.free, asset.ticker.symbol)
                result.append({'value': str(wallet.id),
                               'text': wallet.name,
                               'sort': asset.free,
                               'free': asset.free,
                               'subtext': f'({quantity})'})

    if result:
        result = sorted(result,
                        key=lambda wallet: wallet.get('sort'), reverse=True)
    else:
        result = {'message': gettext('В кошельках нет свободных остатков')}

    return json.dumps(result)


@bp.route('/wallets_to_buy', methods=['GET'])
@login_required
def wallets_to_buy():
    result = []

    for wallet in current_user.wallets:
        wallet.update_price()
        cost_now = smart_round(wallet.cost_now, 1)
        result.append({'value': wallet.id,
                       'text': wallet.name,
                       'sort': cost_now,
                       'subtext': f"(~ {currency_quantity(cost_now)})"})

    result = sorted(result, key=lambda wallet: wallet.get('sort'),
                    reverse=True)
    return json.dumps(result)


@bp.route('/wallets_to_transfer_out', methods=['GET'])
@login_required
def wallets_to_transfer_out():
    wallet_id = request.args['wallet_id']
    ticker_id = request.args['ticker_id']
    result = []

    if len(current_user.wallets) == 1:
        return json.dumps({'message': gettext('У вас только один кошелек')})

    for wallet in current_user.wallets:
        if int(wallet_id) == wallet.id:
            continue

        quantity = sort = 0
        for asset in wallet.assets:
            if ticker_id != asset.ticker_id:
                continue

            quantity = currency_price(asset.free, asset.ticker.symbol)
            sort = asset.free
        info = {'value': str(wallet.id), 'text': wallet.name, 'sort': sort}
        if sort > 0:
            info['subtext'] = f"({quantity})"
        result.append(info)

    if result:
        result = sorted(result,
                        key=lambda wallet_: wallet_.get('sort'), reverse=True)

    return json.dumps(result)


@bp.route('/wallet_assets', methods=['GET'])
@login_required
def wallet_assets():
    result = []
    in_wallet = []
    wallet = Wallet.get(request.args.get('wallet_id'))
    if not wallet:
        return json.dumps({'message': gettext('Выберите кошелек')})

    wallet.update_price()
    assets = wallet.assets
    assets = sorted(assets, key=lambda asset: asset.free, reverse=True)
    for asset in assets:
        if asset.free:
            result.append({'value': asset.ticker.id,
                           'text': asset.ticker.symbol.upper(),
                           'subtext': f'({asset.free})',
                           'free': asset.free,
                           'info': asset.ticker.price})
            in_wallet.append(asset.ticker.id)

    tickers = db.select(Ticker)
    tickers = tickers.where(Ticker.id.not_in(in_wallet))
    tickers = tickers.order_by(Ticker.market_cap_rank.is_(None),
                               Ticker.market_cap_rank.asc())
    # search = request.args.get('search')
    # page = request.args.get('page', 1, type=int)
    #
    # if search:
    #     tickers = tickers.filter(Ticker.name.contains(search) |
    #                              Ticker.symbol.contains(search))

    # tickers = db.paginate(tickers, page=page, per_page=20, error_out=False)
    tickers = db.session.execute(tickers).scalars()
    for t in tickers:
        # result.append({'value': t.id,
        #                'text': t.symbol.upper(),
        #                'subtext': t.name})
        result.append({'value': t.id,
                       'text': t.symbol.upper(),
                       'subtext': t.name,
                       'info': t.price})

    # if not result:
    #     return json.dumps({'message': gettext('Нет активов в кошельке')})

    return json.dumps(result)

