import json
from flask import flash, render_template, request, Blueprint
from flask_login import login_required, current_user
from portfolio_tracker.app import db
from portfolio_tracker.general_functions import get_price_list
from portfolio_tracker.general_functions import dict_get_or_other, float_or_other
from portfolio_tracker.models import Wallet
from portfolio_tracker.wraps import demo_user_change


wallet = Blueprint('wallet',
                   __name__,
                   template_folder='templates',
                   static_folder='static')


def get_user_wallet(id):
    if id:
        return db.session.execute(
                db.select(Wallet).filter_by(id=id,
                                            user_id=current_user.id)).scalar()
    return None


@wallet.route('', methods=['GET'])
@login_required
@demo_user_change
def wallets():
    """ Wallets page """
    wallets = {}
    all = {'total_spent': 0,
           'in_orders': 0,
           'cost_now': 0,
           'money_all': 0}

    for user_wallet in current_user.wallets:
        wallets[user_wallet.id] = {'name': user_wallet.name,
                                   'money_all': user_wallet.money_all,
                                   'cost_now': 0,
                                   'total_spent': 0,
                                   'in_orders': 0,
                                   'free': user_wallet.money_all,
                                   'can_delete': False if user_wallet.money_all else True}
        all['money_all'] += user_wallet.money_all

    for portfolio in current_user.portfolios:
        price_list = get_price_list(portfolio.market_id)

        for asset in portfolio.assets:
            for transaction in asset.transactions:
                wallet = wallets[transaction.wallet.id]
                wallet['can_delete'] = False

                if transaction.order:
                    wallet['in_orders'] += transaction.total_spent
                    all['in_orders'] += transaction.total_spent
                    continue

                price = dict_get_or_other(price_list,
                                          transaction.asset.ticker_id, 0)
                wallet['total_spent'] += transaction.total_spent
                wallet['cost_now'] += transaction.quantity * price
                wallet['free'] -= transaction.total_spent
                all['total_spent'] += transaction.total_spent
                all['cost_now'] += transaction.quantity * price

    all['free'] = all['money_all'] - all['total_spent'] - all['in_orders']
    all['profit'] = all['cost_now'] - all['total_spent'] - all['in_orders']

    return render_template('wallet/wallets.html', all=all, wallets=wallets)


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

    if not current_user.wallets:
        db.session.add(Wallet(name='Default', user_id=current_user.id))

    db.session.commit()
    return ''


@wallet.route('/wallet_settings', methods=['GET'])
@login_required
@demo_user_change
def wallet_settings():
    wallet = get_user_wallet(request.args.get('wallet_id'))
    return render_template('wallet/wallet_settings.html', wallet=wallet)


@wallet.route('/wallet_settings_update', methods=['POST'])
@login_required
@demo_user_change
def wallet_settings_update():
    """ Add or change wallet """
    wallet = get_user_wallet(request.args.get('wallet_id'))
    if not wallet:
        wallet = Wallet(user_id=current_user.id)
        db.session.add(wallet)

    wallet.name = request.form.get('name')
    wallet.money_all = dict_get_or_other(request.form, 'money_all', 0)

    db.session.commit()
    return ''


@wallet.route('/<string:wallet_id>')
@login_required
@demo_user_change
def wallet_info(wallet_id):
    """ Wallet page """
    user_wallet = get_user_wallet(wallet_id)
    if not user_wallet:
        return ''

    wallet = {'name': user_wallet.name,
              'total_spent': 0,
              'cost_now': 0,
              'in_orders': 0}

    asset_list = {}

    for transaction in user_wallet.transactions:
        ticker = transaction.asset.ticker_id

        if not asset_list.get(ticker):
            asset_list[ticker] = {'name': transaction.asset.ticker.name,
                                  'symbol': transaction.asset.ticker.symbol,
                                  'ticker': ticker,
                                  'quantity': 0,
                                  'cost_now': 0,
                                  'total_spent': 0,
                                  'in_orders': 0}
            if transaction.asset.ticker.image:
                asset_list[ticker]['image'] = transaction.asset.ticker.image

        asset = asset_list[ticker]

        if transaction.order:
            asset['in_orders'] += transaction.total_spent
            wallet['in_orders'] += transaction.total_spent
            continue

        price_list = get_price_list(transaction.asset.ticker.market_id)
        price = float_or_other(price_list.get(ticker), 0)
        asset['quantity'] += transaction.quantity
        asset['cost_now'] += transaction.quantity * price
        asset['total_spent'] += transaction.total_spent

        wallet['cost_now'] += transaction.quantity * price
        wallet['total_spent'] += transaction.total_spent

    wallet['free'] = user_wallet.money_all
    wallet['free'] -= wallet['total_spent'] + wallet['in_orders']
    wallet['profit'] = wallet['cost_now']
    wallet['profit'] -= wallet['total_spent'] + wallet['in_orders']

    return render_template('wallet/wallet_info.html',
                           wallet=wallet,
                           assets_list=asset_list)


@wallet.route('/in_out_get', methods=['GET'])
@login_required
@demo_user_change
def wallet_in_out_get():
    return render_template('wallet/wallet_in_out.html')


@wallet.route('/transfer_get', methods=['GET'])
@login_required
@demo_user_change
def wallet_transfer_get():
    return render_template('wallet/wallet_transfer.html')


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
    return ''


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
    return ''


# @wallet.route('/ajax_user_wallets', methods=['GET'])
# @login_required
# def get_all_user_wallets():
#     result = {'results': []}
#
#     for wallet in current_user.wallets:
#         result['results'].append({'id': str(wallet.id),
#                                   'text': wallet.name}) 
#
#     return json.dumps(result, ensure_ascii=False)


@wallet.route('/ajax_user_wallets2', methods=['GET'])
@login_required
def get_all_user_wallets():
    result = []

    for wallet in current_user.wallets:
        result.append({'value': str(wallet.id),
                       'text': wallet.name}) 

    return json.dumps(result, ensure_ascii=False)
