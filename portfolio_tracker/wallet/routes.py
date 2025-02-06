from flask import abort, render_template, request, session
from flask_login import current_user as user, login_required

from ..services import user_object_search_engine as ose
from ..general_functions import actions_on_objects
from ..wraps import closed_for_demo_user
from .services.wallets import Wallets
from . import bp


@bp.route('/', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def wallets():
    """Wallets page and actions on wallets."""

    # Actions
    if request.method == 'POST':
        actions_on_objects(request.data, user.service.get_wallet)

        user.service.create_default_wallet()
        return ''

    return render_template('wallet/wallets.html', wallets=Wallets(user))  # type: ignore


@bp.route('/wallet_settings', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def wallet_settings():
    """Wallet settings."""
    wallet = ose.get_wallet(**request.args, create=True) or abort(404)

    # Apply settings
    if request.method == 'POST':
        wallet.service.edit(request.form)
        return ''

    return render_template('wallet/wallet_settings.html', wallet=wallet)


@bp.route('/wallet_info', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def wallet_info():
    """Wallet page and actions on assets."""
    wallet = ose.get_wallet(**request.args) or abort(404)

    # Actions
    if request.method == 'POST':
        actions_on_objects(request.data, wallet.service.get_asset)
        return ''

    wallet.service.update_price()
    return render_template('wallet/wallet_info.html', wallet=wallet)


@bp.route('/asset_info', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_info():
    """Asset page and actions on transactions."""
    asset = ose.get_wallet_asset(**request.args) or abort(404)

    # Actions
    if request.method == 'POST':
        actions_on_objects(request.data, asset.service.get_transaction)
        return ''

    return render_template('wallet/asset_info.html', asset=asset)


@bp.route('/transaction_info', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def transaction_info():
    """Transaction info."""
    transaction = ose.get_wallet_transaction(**request.args, create=True) or abort(404)

    # Apply transaction
    if request.method == 'POST':
        transaction.service.edit(request.form)
        return ''

    calc_type = session.get('transaction_calculation_type', 'amount')
    return render_template('portfolio/transaction.html',
                           transaction=transaction, asset=transaction.wallet_asset,
                           calculation_type=calc_type)
