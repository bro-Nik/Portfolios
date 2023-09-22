import json
from flask import flash, render_template, request, Blueprint
from flask_babel import gettext
from flask_login import login_required, current_user
from portfolio_tracker.app import db
from portfolio_tracker.general_functions import get_price_list, float_
from portfolio_tracker.models import Wallet
from portfolio_tracker.portfolio.portfolio import delete_transaction
from portfolio_tracker.wraps import demo_user_change


wallet = Blueprint('wallet',
                   __name__,
                   template_folder='templates',
                   static_folder='static')


def get_wallet(id):
    if id:
        return db.session.execute(
                db.select(Wallet).filter_by(id=id,
                                            user_id=current_user.id)).scalar()
    return None


class AllWallets:
    def __init__(self):
        price_list = get_price_list()
        self.total_spent = 0
        self.cost_now = 0
        self.in_orders = 0
        self.free_money = 0

        for wallet in current_user.wallets:
            wallet.update_details(price_list)
            self.total_spent += wallet.total_spent
            self.cost_now += wallet.cost_now
            self.in_orders += wallet.in_orders
            self.free_money += wallet.free_money

        self.total_spent = int(self.total_spent)
        self.cost_now = int(self.cost_now)
        self.in_orders = int(self.in_orders)
        self.free_money = int(self.free_money)

        if self.cost_now > self.total_spent:
            self.color = 'text-green'
        elif self.cost_now < self.total_spent:
            self.color = 'text-red'


@wallet.route('', methods=['GET'])
@login_required
def wallets():
    """ Wallets page """
    return render_template('wallet/wallets.html', all_wallets=AllWallets())


@wallet.route('/action', methods=['POST'])
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
                flash(gettext('Wallet %(name)s is not empty',
                               name=wallet.name), 'danger')
            else:
                for transaction in wallet.transactions:
                    delete_transaction(transaction)
                db.session.delete(wallet)

    if not current_user.wallets:
        current_user.wallets.append(Wallet(name=gettext('Default Wallet')))

    db.session.commit()
    return ''


@wallet.route('/wallet_settings', methods=['GET'])
@login_required
def wallet_settings():
    wallet = get_wallet(request.args.get('wallet_id'))
    return render_template('wallet/wallet_settings.html', wallet=wallet)


@wallet.route('/wallet_settings_update', methods=['POST'])
@login_required
@demo_user_change
def wallet_settings_update():
    """ Add or change wallet """
    wallet = get_wallet(request.args.get('wallet_id'))
    if not wallet:
        wallet = Wallet(user_id=current_user.id)
        db.session.add(wallet)

    name = request.form.get('name')
    money_all = request.form.get('money_all')
    if name is not None:
        wallet.name = name
    if money_all is not None:
        wallet.money_all = float_(money_all, 0)
    wallet.comment = request.form.get('comment')

    db.session.commit()
    return ''


@wallet.route('/<string:wallet_id>')
@login_required
def wallet_info(wallet_id):
    """ Wallet page """
    wallet = get_wallet(wallet_id)
    if not wallet:
        return ''

    wallet.update_details(get_price_list())

    return render_template('wallet/wallet_info.html', wallet=wallet)


@wallet.route('/in_out_get', methods=['GET'])
@login_required
def wallet_in_out_get():
    return render_template('wallet/wallet_in_out.html')


@wallet.route('/transfer_get', methods=['GET'])
@login_required
def wallet_transfer_get():
    return render_template('wallet/wallet_transfer.html')


@wallet.route('/in_out', methods=['POST'])
@login_required
@demo_user_change
def wallet_in_out():
    """ Input output wallet """
    wallet = get_wallet(request.form['wallet_id'])
    if wallet:
        type = int(request.form['type'])
        sum = float_(request.form.get('transfer_amount')) * type
        wallet.money_all += sum
        db.session.commit()
    return ''


@wallet.route('/transfer', methods=['POST'])
@login_required
@demo_user_change
def wallet_transfer():
    """ Transfer wallet """
    sum = float_(request.form.get('transfer_amount'))

    wallet_out = get_wallet(request.form.get('wallet_out'))
    wallet_input = get_wallet(request.form.get('wallet_in'))
    if wallet_out and wallet_input and wallet_out != wallet_input:
        wallet_out.money_all -= sum
        wallet_input.money_all += sum
        db.session.commit()
    return ''


@wallet.route('/ajax_user_wallets', methods=['GET'])
@login_required
def get_all_user_wallets():
    result = []

    for wallet in current_user.wallets:
        result.append({'value': str(wallet.id),
                       'text': wallet.name}) 

    return json.dumps(result, ensure_ascii=False)
