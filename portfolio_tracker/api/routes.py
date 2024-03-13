import json
from datetime import datetime, timezone

from flask import request
from flask_babel import gettext
from flask_login import current_user, login_required

from ..app import db
from ..jinja_filters import currency_quantity, currency_price, smart_round
from ..general_functions import remove_prefix
from ..portfolio.models import Ticker
from ..wallet.utils import get_wallet, last_wallet_transaction
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
    currencies = db.session.execute(
        db.select(Ticker).filter_by(market=market)).scalars()

    for currency in currencies:
        result.append({'value': remove_prefix(currency.id, market),
                       'text': currency.symbol.upper(),
                       'subtext': currency.name})
    return json.dumps(result, ensure_ascii=False)


@bp.route('/wallets_to_sell', methods=['GET'])
@login_required
def wallets_to_sell():
    ticker_id = request.args['ticker_id']
    result = []

    for wallet in current_user.wallets:
        wallet.update_price()

        for asset in wallet.wallet_assets:
            if ticker_id != asset.ticker_id:
                continue

            if asset.free:
                quantity = other_currency(asset.free, asset.ticker.symbol)
                result.append({'value': str(wallet.id),
                               'text': wallet.name,
                               'sort': asset.free,
                               'subtext': f'({quantity})'})

    if result:
        result = sorted(result,
                        key=lambda wallet_: wallet_.get('sort'), reverse=True)
    else:
        result = {'message': gettext('В кошельках нет свободных остатков')}

    return json.dumps(result)


@bp.route('/wallets_to_buy', methods=['GET'])
@login_required
def wallets_to_buy():
    result = []

    for wallet in current_user.wallets:
        wallet.update_price()

        free = smart_round(wallet.free, 1)
        result.append({'value': str(wallet.id),
                       'text': wallet.name,
                       'sort': wallet.free,
                       'subtext': f"(~ {currency_quantity(free)})"})

    result = sorted(result, key=lambda wallet_: wallet_.get('sort'),
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

        wallet.update_price()

        quantity = sort = 0
        for asset in wallet.wallet_assets:
            if ticker_id != asset.ticker_id:
                continue

            quantity = other_currency(asset.free, asset.ticker.symbol)
            sort = asset.free
        info = {'value': str(wallet.id), 'text': wallet.name, 'sort': sort}
        if sort > 0:
            info['subtext'] = f"({quantity})"
        result.append(info)

    if result:
        result = sorted(result,
                        key=lambda wallet_: wallet_.get('sort'), reverse=True)

    return json.dumps(result)


@bp.route('/wallet_stable_assets', methods=['GET'])
@login_required
def wallet_stable_assets():
    result = []
    wallet = get_wallet(request.args.get('wallet_id'))
    last_type = request.args.get('last')

    if last_type:
        last_transaction = last_wallet_transaction(wallet, last_type)
        if last_transaction:
            ticker = last_transaction.quote_ticker
        else:
            ticker = current_user.currency_ticker

        result = {'value': ticker.id,
                  'text': ticker.symbol.upper(),
                  'info': ticker.price}
        return json.dumps(result)

    if wallet:
        wallet.update_price()
        stables = wallet.stable_assets
        stables = sorted(stables, key=lambda asset_: asset_.free, reverse=True)
        for asset in stables:
            result.append({'value': asset.ticker.id,
                           'text': asset.ticker.symbol.upper(),
                           'subtext': f'(~ {int(asset.free)})',
                           'info': asset.ticker.price})

    if not result:
        result = {'message': gettext('Нет активов в кошельке')}

    return json.dumps(result)
