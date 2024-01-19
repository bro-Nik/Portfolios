import json
from datetime import datetime, timezone

from flask import render_template, request, url_for
from flask_login import login_required

from ..wraps import demo_user_change
from ..portfolio.models import Ticker, Transaction
from ..portfolio.utils import create_new_transaction
from .models import db
from .utils import AllWallets, actions_on_assets, actions_on_transactions, \
    actions_on_wallets, create_new_wallet, get_transaction, get_wallet, \
    get_wallet_asset
from . import bp


@bp.route('/', methods=['GET'])
@login_required
def wallets():
    all_wallets = AllWallets()
    all_wallets.update_price()
    return render_template('wallet/wallets.html', all_wallets=all_wallets)


@bp.route('/action', methods=['POST'])
@login_required
@demo_user_change
def wallets_action():
    data = json.loads(request.data) if request.data else {}

    actions_on_wallets(data['ids'], data['action'])
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

    actions_on_assets(wallet, data['ids'], data['action'])
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

    query = (Ticker.query.filter_by(stable=True).order_by(Ticker.id))
    # .order_by(Ticker.market_cap_rank.nulls_last(), Ticker.id))

    if search:
        query = query.filter(Ticker.name.contains(search)
                             | Ticker.symbol.contains(search))

    tickers = query.paginate(page=request.args.get('page', 1, type=int),
                             per_page=20,
                             error_out=False)
    if tuple(tickers):
        return render_template('wallet/add_stable_tickers.html',
                               tickers=tickers)
    return 'end'


@bp.route('/add_stable', methods=['GET'])
@login_required
def stable_add():
    ticker_id = request.args.get('ticker_id')
    wallet = get_wallet(request.args.get('wallet_id'))
    asset = get_wallet_asset(wallet, ticker_id, create=True)

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
            date=datetime.now(timezone.utc)
        )
    return render_template('wallet/transaction.html',
                           asset=asset, transaction=transaction)


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
            'type': ('TransferOut' if transaction.type == 'TransferIn'
                     else 'TransferIn'),
            'date': transaction.date,
            'quantity': transaction.quantity * -1
        })

        transaction2.update_dependencies()

        transaction.related_transaction.append(transaction2)

    db.session.commit()
    return ''


@bp.route('/transactions_action', methods=['POST'])
@login_required
@demo_user_change
def transactions_action():
    wallet = get_wallet(request.args.get('wallet_id'))
    asset = get_wallet_asset(wallet, request.args.get('ticker_id'))
    data = json.loads(request.data) if request.data else {}

    actions_on_transactions(asset, data['ids'], data['action'])
    return ''
