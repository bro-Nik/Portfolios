import json
from flask import flash, render_template, redirect, url_for, request, Blueprint
from flask_login import login_required, current_user
from portfolio_tracker.app import db
from portfolio_tracker.general_functions import price_list_def
from portfolio_tracker.general_functions import dict_get_or_other, float_or_other
from portfolio_tracker.models import Wallet
from portfolio_tracker.wraps import demo_user_change


wallet = Blueprint('wallet', __name__, template_folder='templates', static_folder='static')


def get_user_wallet(id):
    if not id:
        return None
    return db.session.execute(
            db.select(Wallet).filter_by(id=id,
                                        user_id=current_user.id)).scalar()


@wallet.route('/wallets', methods=['GET'])
@login_required
def wallets():
    """ Wallets page """
    price_list = price_list_def()
    holder_list = {}
    total_spent = 0

    for portfolio in current_user.portfolios:
        for asset in portfolio.assets:
            for transaction in asset.transactions:
                if transaction.order:
                    continue

                price = dict_get_or_other(price_list,
                                          transaction.asset.ticker_id, 0)
                if not holder_list.get(transaction.wallet.name):
                    holder_list[transaction.wallet.name] = 0
                holder_list[transaction.wallet.name] += transaction.quantity * price
                total_spent += transaction.total_spent

    return render_template('wallet/wallets.html',
                           holder_list=holder_list,
                           total_spent=total_spent)


@wallet.route('/wallet_settings', methods=['GET'])
@login_required
def wallet_settings():
    wallet = get_user_wallet(request.args.get('wallet_id'))

    return render_template('wallet/wallet_settings.html', wallet=wallet)


@wallet.route('/update', methods=['POST'])
@login_required
@demo_user_change
def wallet_update():
    """ Add or change wallet """
    wallet = get_user_wallet(request.args.get('wallet_id'))
    if not wallet:
        wallet = Wallet(user_id=current_user.id)
        db.session.add(wallet)

    wallet.name = request.form.get('name')
    wallet.money_all = dict_get_or_other(request.form, 'money_all', 0)

    db.session.commit()

    return redirect(url_for('.wallets'))


@wallet.route('/action', methods=['POST'])
@login_required
@demo_user_change
def wallets_action():
    data = json.loads(request.data) if request.data else {}
    ids = data.get('ids')

    for id in ids:
        wallet = get_user_wallet(id)
        if not wallet:
            continue

        if wallet.money_all > 0 or wallet.transactions:
            flash('В кошельке ' + wallet.name + ' есть остатки')
        else:
            db.session.delete(wallet)

    db.session.commit()
    return redirect(url_for('.wallets'))


@wallet.route('/<string:wallet_id>')
@login_required
def wallet_info(wallet_id):
    """ Wallet page """
    price_list = price_list_def()
    wallet = get_user_wallet(wallet_id)
    assets_list = {}
    wallet_cost_now = 0

    for portfolio in current_user.portfolios:
        for asset in portfolio.assets:
            for transaction in asset.transactions:
                if transaction.order and transaction.type == 'Продажа':
                    continue

                if transaction.wallet != wallet:
                    continue
                
                ticker = transaction.asset.ticker_id
                if not assets_list.get(ticker):
                    assets_list[ticker] = {
                        'name': transaction.asset.ticker.name,
                        'symbol': transaction.asset.ticker.symbol,
                        'order': 0,
                        'quantity': 0
                    }

                if transaction.order:
                    assets_list[ticker]['order'] += transaction.total_spent
                else:
                    assets_list[ticker]['quantity'] += transaction.quantity

                price = price_list.get(ticker)
                if not price:
                    price = 0
                    price_list[ticker] = 0
                wallet_cost_now += float(transaction.quantity) * price

    return render_template('wallet/wallet_info.html',
                           wallet=wallet,
                           assets_list=assets_list,
                           price_list=price_list,
                           wallet_cost_now=wallet_cost_now)


@wallet.route('/in_out', methods=['POST'])
@login_required
@demo_user_change
def wallet_in_out():
    """ Input output wallet """
    wallet = get_user_wallet(request.form.get('wallet_id'))
    if wallet:
        type = request.form.get('type')
        sum = float_or_other(request.form.get('transfer_amount'))
        sum = sum if type == 'Ввод' else -1 * sum
        wallet.money_all += sum
        db.session.commit()
    return redirect(url_for('.wallets'))


@wallet.route('/transfer', methods=['POST'])
@login_required
@demo_user_change
def wallet_transfer():
    """ Transfer wallet """
    sum = float_or_other(request.form.get('transfer_amount'))

    wallet_out = get_user_wallet(request.form.get('wallet_out'))
    wallet_input = get_user_wallet(request.form.get('wallet_in'))
    if wallet_out and wallet_input and wallet_out != wallet_input:
        wallet_out.money_all -= sum
        wallet_input.money_all += sum
        db.session.commit()
    return redirect(url_for('.wallets'))


@wallet.route('/ajax_user_wallets', methods=['GET'])
@login_required
def get_all_user_wallets():
    result = {'results': []}

    for wallet in current_user.wallets:
        result['results'].append({'id': str(wallet.id),
                                  'text': wallet.name}) 

    return json.dumps(result, ensure_ascii=False)
