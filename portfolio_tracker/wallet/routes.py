from flask import abort, render_template, request, url_for
from flask_login import current_user, login_required

from ..app import db
from ..general_functions import actions_in
from ..wraps import closed_for_demo_user
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

    return render_template('wallet/asset_info.html', asset=asset)
