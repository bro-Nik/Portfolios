from flask import abort, render_template, request, url_for
from flask_login import current_user, login_required

from ..app import db
from ..general_functions import actions_in
from ..wraps import demo_user_change
from ..portfolio.models import Ticker
from ..portfolio.utils import create_new_transaction, get_ticker, \
    get_transaction
from .utils import Wallets, create_wallet, create_wallet_asset, \
    get_wallet, get_wallet_asset
from . import bp


@bp.route('/', methods=['GET', 'POST'])
@login_required
@demo_user_change
def wallets():
    """Wallets page and actions on wallets."""
    # Actions
    if request.method == 'POST':
        actions_in(request.data, get_wallet)

        # Create default wallet
        if not current_user.wallets:
            create_wallet(first=True)
        db.session.commit()
        return ''

    return render_template('wallet/wallets.html', wallets=Wallets())


@bp.route('/wallet_settings', methods=['GET', 'POST'])
@login_required
@demo_user_change
def wallet_settings():
    """Wallet settings."""
    wallet = get_wallet(request.args.get('wallet_id')) or create_wallet()

    # Apply settings
    if request.method == 'POST':
        wallet.edit(request.form)
        db.session.commit()
        return ''

    return render_template('wallet/wallet_settings.html', wallet=wallet)


@bp.route('/wallet_info', methods=['GET', 'POST'])
@login_required
@demo_user_change
def wallet_info():
    """Wallet page and actions on assets."""
    wallet = get_wallet(request.args.get('wallet_id')) or abort(404)

    # Actions
    if request.method == 'POST':
        actions_in(request.data, get_wallet_asset, wallet=wallet)
        db.session.commit()
        return ''

    wallet.update_price()
    return render_template('wallet/wallet_info.html', wallet=wallet)


@bp.route('/asset_info', methods=['GET', 'POST'])
@login_required
@demo_user_change
def asset_info():
    """Asset page and actions on transactions."""
    wallet = get_wallet(request.args.get('wallet_id'))
    asset = get_wallet_asset(request.args.get('asset_id'), wallet,
                             request.args.get('ticker_id')) or abort(404)

    # Actions
    if request.method == 'POST':
        actions_in(request.data, get_transaction, asset=asset)
        db.session.commit()
        return ''

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
        query = query.filter(Ticker.name.contains(search) |
                             Ticker.symbol.contains(search))

    tickers = query.paginate(page=request.args.get('page', 1, type=int),
                             per_page=20, error_out=False)
    if tuple(tickers):
        return render_template('wallet/add_stable_tickers.html',
                               tickers=tickers)
    return 'end'


@bp.route('/add_stable', methods=['GET'])
@login_required
def stable_add():
    ticker_id = request.args.get('ticker_id')
    wallet = get_wallet(request.args.get('wallet_id')) or abort(404)
    asset = get_wallet_asset(wallet=wallet, ticker_id=ticker_id)
    if not asset:
        ticker = get_ticker(ticker_id) or abort(404)
        asset = create_wallet_asset(wallet, ticker.id)
        db.session.commit()

    return str(url_for('.asset_info',
                       only_content=request.args.get('only_content'),
                       wallet_id=wallet.id, ticker_id=ticker.id))


@bp.route('/transaction', methods=['GET', 'POST'])
@login_required
@demo_user_change
def transaction_info():
    wallet = get_wallet(request.args.get('wallet_id'))
    asset = get_wallet_asset(request.args.get('asset_id'), wallet,
                             request.args.get('ticker_id')) or abort(404)
    transaction = get_transaction(request.args.get('transaction_id'), asset
                                  ) or create_new_transaction(asset)

    # Apply transaction
    if request.method == 'POST':
        transaction2 = transaction.related_transaction

        transaction.edit(request.form)
        transaction.update_dependencies()

        # Связанная транзакция
        wallet2 = get_wallet(request.form.get('wallet_id'))
        asset2 = get_wallet_asset(
            wallet=wallet2, ticker_id=asset.ticker_id
        ) or create_wallet_asset(wallet2, asset.ticker_id) if wallet2 else None

        if asset2:
            transaction2 = transaction2 or create_new_transaction(asset2)

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

    return render_template('wallet/transaction.html',
                           asset=asset, transaction=transaction)
