from flask import abort, render_template, request, url_for
from flask_login import current_user, login_required

from ..app import db
from ..general_functions import actions_in
from ..wraps import closed_for_demo_user
from ..portfolio.models import Ticker
from ..wallet.models import Wallet
from .utils import Wallets
from . import bp


@bp.route('/', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def wallets():
    """Wallets page and actions on wallets."""
    # Actions
    if request.method == 'POST':
        actions_in(request.data, Wallet.get)

        # Create default wallet
        if not current_user.wallets:
            wallet = Wallet.create(first=True)
            current_user.wallets.append(wallet)
        db.session.commit()
        return ''

    return render_template('wallet/wallets.html', wallets=Wallets())


@bp.route('/wallet_settings', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def wallet_settings():
    """Wallet settings."""
    wallet = Wallet.get(request.args.get('wallet_id')) or Wallet.create()

    # Apply settings
    if request.method == 'POST':
        if not wallet.id:
            current_user.wallets.append(wallet)

        wallet.edit(request.form)
        db.session.commit()
        return ''

    return render_template('wallet/wallet_settings.html', wallet=wallet)


@bp.route('/wallet_info', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def wallet_info():
    """Wallet page and actions on assets."""
    wallet = Wallet.get(request.args.get('wallet_id')) or abort(404)

    # Actions
    if request.method == 'POST':
        actions_in(request.data, wallet.get_asset)
        db.session.commit()
        return ''

    wallet.update_price()
    return render_template('wallet/wallet_info.html', wallet=wallet)


@bp.route('/asset_info', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_info():
    """Asset page and actions on transactions."""
    wallet = Wallet.get(request.args.get('wallet_id')) or abort(404)
    find_by = request.args.get('ticker_id') or request.args.get('asset_id')
    asset = wallet.get_asset(find_by) or abort(404)

    # Actions
    if request.method == 'POST':
        actions_in(request.data, asset.get_transaction)
        db.session.commit()
        return ''

    # page = 'stable_' if asset.ticker.stable else ''
    return render_template('wallet/asset_info.html', asset=asset)


@bp.route('/add_stable', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def stable_add():
    wallet_id = request.args.get('wallet_id')

    if request.method == 'POST':
        ticker_id = request.args.get('ticker_id')
        wallet = Wallet.get(wallet_id) or abort(404)
        asset = wallet.get_asset(ticker_id)
        if not asset:
            ticker = Ticker.get(ticker_id) or abort(404)
            asset = wallet.create_asset(ticker)
            wallet.wallet_assets.append(asset)
            db.session.commit()

        return str(url_for('.asset_info',
                           only_content=request.args.get('only_content'),
                           wallet_id=wallet.id, ticker_id=ticker.id))

    return render_template('wallet/add_stable_modal.html', wallet_id=wallet_id)


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


@bp.route('/transaction', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def transaction_info():
    wallet = Wallet.get(request.args.get('wallet_id')) or abort(404)
    find_by = request.args.get('ticker_id') or request.args.get('asset_id')
    asset = wallet.get_asset(find_by) or abort(404)
    transaction = asset.get_transaction(request.args.get('transaction_id')
                                        ) or asset.create_transaction()

    # Apply transaction
    if request.method == 'POST':
        transaction2 = transaction.related_transaction

        if not transaction.id:
            asset.transactions.append(transaction)
            db.session.add(transaction)
        transaction.edit(request.form)
        transaction.update_dependencies()

        # Связанная транзакция
        wallet2 = Wallet.get(request.form.get('wallet_id'))
        if wallet2:
            asset2 = wallet2.get_asset(asset.ticker_id)
            if not asset2:
                ticker2 = Ticker.get(asset.ticker_id) or abort(404)
                asset2 = wallet2.create_asset(ticker2)
                wallet2.wallet_assets.append(asset2)

            if not transaction2:
                transaction2 = asset2.create_transaction()
                asset2.transactions.append(transaction2)
                db.session.add(transaction2)

            transaction2.edit({
                'type': ('TransferOut' if transaction.type == 'TransferIn'
                         else 'TransferIn'),
                'date': transaction.date,
                'quantity': transaction.quantity * -1
            })

            transaction2.update_dependencies()

            db.session.flush()
            transaction.related_transaction_id = transaction2.id
            transaction2.related_transaction_id = transaction.id

        db.session.commit()
        return ''

    return render_template('wallet/transaction.html',
                           asset=asset, transaction=transaction)
