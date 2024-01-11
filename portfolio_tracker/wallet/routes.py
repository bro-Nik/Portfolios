import json
from datetime import datetime
from flask import flash, render_template, request, url_for
from flask_babel import gettext
from flask_login import login_required, current_user
from portfolio_tracker.app import db
from portfolio_tracker.jinja_filters import other_currency, user_currency
from portfolio_tracker.models import Ticker, Transaction
from portfolio_tracker.wallet.utils import AllWallets, create_new_wallet, \
    create_new_transaction, get_transaction, get_wallet, get_wallet_asset, \
    last_wallet_transaction
from portfolio_tracker.wraps import demo_user_change
from portfolio_tracker.wallet import bp


@bp.route('', methods=['GET'])
@login_required
def wallets():
    return render_template('wallet/wallets.html', all_wallets=AllWallets())


@bp.route('/action', methods=['POST'])
@login_required
@demo_user_change
def wallets_action():
    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data['action']

    for id in ids:
        wallet = get_wallet(id)
        if not wallet:
            continue

        if 'delete' in action:
            if 'with_contents' not in action and not wallet.is_empty():
                flash(gettext('Кошелек %(name)s не пустой',
                              name=wallet.name), 'danger')
            else:
                wallet.delete()

    db.session.commit()
    if not current_user.wallets:
        current_user.create_first_wallet()
        db.session.commit()
    return ''


@bp.route('/wallet_settings', methods=['GET'])
@login_required
def wallet_settings():
    wallet = get_wallet(request.args.get('wallet_id'))
    return render_template('wallet/wallet_settings.html', wallet=wallet)


@bp.route('/wallet_settings_update', methods=['POST'])
@login_required
@demo_user_change
def wallet_settings_update():
    wallet = get_wallet(request.args.get('wallet_id'))
    if not wallet:
        wallet = create_new_wallet()

    wallet.edit(request.form)
    return ''


@bp.route('/wallet_info', methods=['GET'])
@login_required
def wallet_info():
    """ Wallet page """
    wallet = get_wallet(request.args.get('wallet_id'))
    if not wallet:
        return ''

    wallet.update_price()
    return render_template('wallet/wallet_info.html', wallet=wallet)


@bp.route('/assets_action', methods=['POST'])
@login_required
@demo_user_change
def assets_action():
    """ Asset action """
    wallet = get_wallet(request.args.get('wallet_id'))

    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data['action']

    for ticker_id in ids:
        asset = get_wallet_asset(wallet, ticker_id)
        if not asset:
            continue

        if 'delete' in action:
            if 'with_contents' not in action and not asset.is_empty():
                flash(gettext('В активе %(name)s есть транзакции',
                              name=asset.ticker.name), 'danger')
            else:
                asset.delete()

    db.session.commit()
    return ''


@bp.route('/asset_info', methods=['GET'])
@login_required
def asset_info():
    wallet = get_wallet(request.args.get('wallet_id'))
    asset = get_wallet_asset(wallet, request.args.get('ticker_id'))
    if not asset:
        return ''

    asset.update_price()

    page = 'stable_' if asset.ticker.stable else ''
    return render_template(f'wallet/{page}asset_info.html', asset=asset)


@bp.route('/add_stable_modal', methods=['GET'])
@login_required
def stable_add_modal():
    return render_template('wallet/add_stable_modal.html',
                           wallet_id=request.args.get('wallet_id'))


@bp.route('/add_stable_tickers', methods=['GET'])
@login_required
def stable_add_tickers():
    search = request.args.get('search')

    query = (Ticker.query.filter(Ticker.stable == True)
             .order_by(Ticker.id))
    # .order_by(Ticker.market_cap_rank.nulls_last(), Ticker.id))

    if search:
        query = query.filter(Ticker.name.contains(search)
                             | Ticker.symbol.contains(search))
    print(query.all())

    tickers = query.paginate(page=request.args.get('page', 1, type=int),
                             per_page=20,
                             error_out=False)
    if tuple(tickers):
        print('tuple')
        print(tuple(tickers))
        return render_template('wallet/add_stable_tickers.html',
                               tickers=tickers)
    print('end')
    return 'end'


@bp.route('/add_stable', methods=['GET'])
@login_required
def stable_add():
    wallet = get_wallet(request.args.get('wallet_id'))
    asset = get_wallet_asset(wallet, request.args.get('ticker_id'), create=True)

    return str(url_for('.asset_info',
                       only_content=request.args.get('only_content'),
                       wallet_id=asset.wallet_id,
                       ticker_id=asset.ticker_id)) if asset else ''


@bp.route('/transaction', methods=['GET'])
@login_required
def transaction_info():
    wallet = get_wallet(request.args.get('wallet_id'))
    asset = get_wallet_asset(wallet, request.args.get('ticker_id'))
    if not asset:
        return ''

    asset.update_price()
    transaction = get_transaction(asset, request.args.get('transaction_id'))
    if not transaction:
        transaction = Transaction(
            type='Input' if asset.ticker.stable else 'TransferOut',
            date=datetime.utcnow()
        )
    return render_template('wallet/transaction.html',
                           asset=asset,
                           transaction=transaction)


@bp.route('/transaction_update', methods=['POST'])
@login_required
@demo_user_change
def transaction_update():
    wallet = get_wallet(request.args.get('wallet_id'))
    asset = get_wallet_asset(wallet, request.args.get('ticker_id'))
    if not wallet or not asset:
        return ''

    transaction = get_transaction(asset, request.args.get('transaction_id'))
    transaction2 = None

    if transaction:
        transaction.update_dependencies('cancel')

        if transaction.related_transaction:
            transaction2 = transaction.related_transaction
            transaction2.update_dependencies('cancel')

    else:
        transaction = create_new_transaction(asset)

    transaction.edit(request.form)
    transaction.update_dependencies()

    # Связанная транзакция
    wallet2 = get_wallet(request.form.get('wallet_id'))
    asset2 = get_wallet_asset(wallet2, asset.ticker_id, create=True)

    if wallet2 and asset2:
        if not transaction2:
            transaction2 = create_new_transaction(asset2)

        transaction2.edit({
            'type': 'TransferOut' if transaction.type == 'TransferIn' else 'TransferIn',
            'date': transaction.date,
            'quantity': transaction.quantity * -1
        })

        transaction2.update_dependencies()

        transaction.related_transaction.append(transaction2)
        # transaction.related_transaction_id = transaction2.id
        # transaction2.related_transaction_id = transaction.id

    db.session.commit()
    return ''


@bp.route('/transactions_action', methods=['POST'])
@login_required
@demo_user_change
def transactions_action():
    wallet = get_wallet(request.args.get('wallet_id'))
    asset = get_wallet_asset(wallet, request.args.get('ticker_id'))

    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data['action']

    for id in ids:
        transaction = get_transaction(asset, id)
        if not transaction:
            continue

        if 'delete' in action:
            transaction.delete()

    db.session.commit()
    return ''


@bp.route('/ajax_wallets_to_sell', methods=['GET'])
@login_required
def get_wallets_to_sell():
    ticker_id = request.args['ticker_id']
    result = []

    for wallet in current_user.wallets:
        wallet.update_price()

        for asset in wallet.wallet_assets:
            if ticker_id != asset.ticker.id:
                continue

            if asset.free:
                quantity = other_currency(asset.free, asset.ticker.symbol)
                result.append({'value': str(wallet.id),
                               'text': wallet.name,
                               'sort': asset.free,
                               'subtext': f'({quantity})'})

    if result:
        result = sorted(result,
                        key=lambda wallet: wallet.get('sort'), reverse=True)
    else:
        result = {'message': gettext('В кошельках нет свободных остатков')}

    return json.dumps(result)


@bp.route('/ajax_wallets_to_buy', methods=['GET'])
@login_required
def get_wallets_to_buy():
    result = []

    for wallet in current_user.wallets:
        wallet.update_price()

        result.append({'value': str(wallet.id),
                       'text': wallet.name,
                       'sort': wallet.free,
                       'subtext': f"(~ {user_currency(wallet.free, 'big')})"})

    result = sorted(result,
                    key=lambda wallet: wallet.get('sort'), reverse=True)

    return json.dumps(result)


@bp.route('/ajax_wallets_to_transfer_out', methods=['GET'])
@login_required
def get_wallets_to_transfer_out():
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
            if ticker_id != asset.ticker.id:
                continue

            quantity = other_currency(asset.free, asset.ticker.symbol)
            sort = asset.free
        info = {'value': str(wallet.id), 'text': wallet.name, 'sort': sort}
        if sort > 0:
            info['subtext'] = f"({quantity})"
        result.append(info)

    if result:
        result = sorted(result,
                        key=lambda wallet: wallet.get('sort'), reverse=True)

    return json.dumps(result)


@bp.route('/ajax_wallet_stable_assets', methods=['GET'])
@login_required
def ajax_wallet_stable_assets():
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
        stables = sorted(stables, key=lambda asset: asset.free, reverse=True)
        for asset in stables:
            result.append({'value': asset.ticker.id,
                           'text': asset.ticker.symbol.upper(),
                           'subtext': f'(~ {int(asset.free)})',
                           'info': asset.ticker.price})

    if not result:
        result = {'message': gettext('Нет активов в кошельке')}

    return json.dumps(result)


@bp.route('/ajax_currencies', methods=['GET'])
@login_required
def ajax_currencies():
    result = []
    currencies = db.session.execute(
        db.select(Ticker).filter_by(market='currency')).scalars()

    for currency in currencies:
        result.append({'value': str(currency.id[3:]),
                       'text': currency.symbol.upper(),
                       'subtext': currency.name})

    return json.dumps(result, ensure_ascii=False)
