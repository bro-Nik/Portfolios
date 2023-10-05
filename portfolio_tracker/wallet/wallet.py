import json
from datetime import datetime, timedelta
from flask import flash, render_template, request, Blueprint, url_for
from flask_babel import gettext
from babel.numbers import format_number, format_decimal, format_percent, parse_decimal, format_currency
from flask_login import login_required, current_user
from portfolio_tracker.app import db
from portfolio_tracker.general_functions import delete_transaction, get_price_list, float_, int_
from portfolio_tracker.jinja_filters import user_currency
from portfolio_tracker.models import Ticker, Wallet, WalletAsset, WalletTransaction
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


def get_wallet_asset(asset_id=None, ticker_id=None, wallet_id=None, create=False):
    if asset_id:
        return db.session.execute(
            db.select(WalletAsset).filter_by(id=asset_id)).scalar()

    ticker = db.session.execute(
        db.select(WalletAsset).filter_by(ticker_id=ticker_id,
                                          wallet_id=wallet_id)).scalar()

    # Вставить проверку на пользователя

    if not ticker and create:
        ticker = WalletAsset(ticker_id=ticker_id,
                              wallet_id=wallet_id)
        db.session.add(ticker)
        db.session.commit()

    return ticker


def get_wallet_transaction(id):
    if id:
        transaction = db.session.execute(
            db.select(WalletTransaction).filter_by(id=id)).scalar()
        if transaction and transaction.wallet_asset.wallet.user_id == current_user.id:
            return transaction
    return None


class AllWallets:
    def __init__(self):
        price_list = get_price_list()
        self.cost_now = 0
        self.in_orders = 0
        self.free = 0

        for wallet in current_user.wallets:
            wallet.update_price(price_list)
            self.cost_now += wallet.cost_now
            self.in_orders += wallet.in_orders
            self.free += wallet.free



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
    if name is not None:
        wallet.name = name
    wallet.comment = request.form.get('comment')

    db.session.commit()
    return ''


@wallet.route('/wallet_<int:wallet_id>')
@login_required
def wallet_info(wallet_id):
    """ Wallet page """
    wallet = get_wallet(wallet_id)
    if not wallet:
        return ''

    wallet.update_price(get_price_list())

    return render_template('wallet/wallet_info.html', wallet=wallet)


@wallet.route('/asset_<int:asset_id>')
@login_required
def asset_info(asset_id):
    asset = get_wallet_asset(asset_id)
    if not asset:
        return ''

    asset.update_price(get_price_list())

    page = 'stable_' if asset.ticker.stable else ''
    return render_template('wallet/' + page + 'asset_info.html', asset=asset)


@wallet.route('/<string:wallet_id>/add_stable_modal', methods=['GET'])
@login_required
def stable_add_modal(wallet_id):
    return render_template('wallet/add_stable_modal.html',
                           wallet_id=wallet_id)


@wallet.route('/add_stable_tickers', methods=['GET'])
@login_required
def stable_add_tickers():
    per_page = 20
    search = request.args.get('search')

    query = (Ticker.query.filter(Ticker.stable == True)
        .order_by(Ticker.market_cap_rank.nulls_last(), Ticker.id))

    if search:
        query = query.filter(Ticker.name.contains(search)
                             | Ticker.symbol.contains(search))

    tickers = query.paginate(page=int_(request.args.get('page'), 1),
                             per_page=per_page,
                             error_out=False)
    if tuple(tickers):
        return render_template('wallet/add_stable_tickers.html',
                               tickers=tickers)
    return 'end'


@wallet.route('/<string:wallet_id>/add_stable', methods=['GET'])
@login_required
def stable_add(wallet_id):
    asset = get_wallet_asset(ticker_id=request.args.get('ticker_id'),
                             wallet_id=wallet_id, create=True)

    return str(url_for('.asset_info',
                asset_id=asset.id,
                only_content=request.args.get('only_content')))


# @wallet.route('/transfer_get', methods=['GET'])
# @login_required
# def wallet_transfer_get():
#     return render_template('wallet/wallet_transfer.html')


# @wallet.route('/transfer_coin', methods=['GET'])
# @login_required
# def wallet_transfer_coin():
#     return render_template('wallet/wallet_transfer_coin.html')


@wallet.route('/asset_<int:asset_id>/transaction', methods=['GET'])
@login_required
def transaction(asset_id):
    asset = get_wallet_asset(asset_id=asset_id)
    asset.get_quantity()
    transaction = get_wallet_transaction(request.args.get('transaction_id'))
    return render_template('wallet/transaction.html',
                           asset=asset,
                           transaction=transaction,
                           date=datetime.now().date())


@wallet.route('/asset_<int:asset_id>/transaction_update', methods=['POST'])
@login_required
@demo_user_change
def transaction_update(asset_id):
    transaction = get_wallet_transaction(request.args.get('transaction_id'))
    if not transaction:
        transaction = WalletTransaction(wallet_asset_id=asset_id)
        db.session.add(transaction)

    transaction.type = request.form['type']
    transaction.date = request.form['date']
    transaction.amount = float(request.form['amount'])
    transaction.amount *= int(transaction.type)

    wallet2_id = request.form.get('wallet_id')
    if wallet2_id:
        asset = get_wallet_asset(asset_id)
        asset2 = get_wallet_asset(ticker_id=asset.ticker_id,
                                  wallet_id=wallet2_id,
                                  create=True)
        transaction2 = WalletTransaction(related_transaction=transaction.id)
        asset2.wallet_transactions.append(transaction2)
        transaction2.type = '-1' if transaction.type == '+1' else '+1'
        transaction2.date = request.form['date']
        transaction2.amount = float(request.form['amount'])
        transaction2.amount *= int(transaction2.type)
        db.session.commit()

        transaction.related_transaction = transaction2.id

    db.session.commit()
    return ''


@wallet.route('/transactions_action', methods=['POST'])
@login_required
@demo_user_change
def transactions_action():
    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data['action']

    for id in ids:
        transaction = get_wallet_transaction(id)
        if not transaction:
            continue

        if 'delete' in action:
            db.session.delete(transaction)

    db.session.commit()
    return ''


# @wallet.route('/transfer', methods=['POST'])
# @login_required
# @demo_user_change
# def wallet_transfer():
#     """ Transfer wallet """
#     pass
    # sum = float_(request.form.get('transfer_amount'))
    #
    # wallet_out = get_wallet(request.form.get('wallet_out'))
    # wallet_input = get_wallet(request.form.get('wallet_in'))
    # if wallet_out and wallet_input and wallet_out != wallet_input:
    #     db.session.commit()
    # return ''


# @wallet.route('/ajax_user_wallets', methods=['GET'])
# @login_required
# def get_all_user_wallets():
#     result = []
#
#     for wallet in current_user.wallets:
#         result.append({'value': str(wallet.id),
#                        'text': wallet.name,
#                        'subtext': '(' + str(wallet.free_money()) + ')'}) 
#
#     return json.dumps(result, ensure_ascii=False)


@wallet.route('/ajax_all_wallets', methods=['GET'])
@login_required
def get_all_wallets():
    price_list = get_price_list()
    with_out_id = request.args.get('with_out_id')
    with_ticker_id = request.args.get('with_ticker_id')
    info = request.args.get('info')
    result = []
    sort = False

    for wallet in current_user.wallets:
        if with_out_id and int(with_out_id) == wallet.id:
            continue

        if with_ticker_id:
            sort = True
            for asset in wallet.wallet_assets:
                if with_ticker_id != asset.ticker.id:
                    continue

                quantity = asset.quantity()
                if quantity:
                    quantity = str(quantity) + ' ' + asset.ticker.symbol.upper()
                    result.append({'value': str(wallet.id),
                                   'text': wallet.name,
                                   'sort': quantity,
                                   'subtext': '(' + quantity + ')'}) 

        else:
            wallet_info = {'value': str(wallet.id), 'text': wallet.name}
            if info == 'free_money':
                sort = True
                free = wallet.free_money(price_list)
                wallet_info['sort'] = 0
                if free:
                    wallet_info['sort'] = free
                    free = user_currency(wallet.free_money(price_list))
                    wallet_info['subtext'] = '(~ ' + free + ')'
            result.append(wallet_info) 

    if sort:
        result = sorted(result,
                        key=lambda wallet: wallet.get('sort'), reverse=True)

    return json.dumps(result)


@wallet.route('/ajax_free_stable', methods=['GET'])
@login_required
def ajax_stable_assets():
    wallet = get_wallet(request.args.get('wallet_id'))
    if not wallet:
        return ''

    stables = db.session.execute(
        db.select(Ticker).filter(Ticker.stable == True)).scalars()

    ids = []
    result = []

    wallet_free_assets = wallet.free_stable()
    wallet_free_assets = sorted(wallet_free_assets,
                                key=lambda asset: asset.free, reverse=True)
    for asset in wallet_free_assets:
        if asset.free:
            free = user_currency(asset.free)
            ids.append(asset.ticker.id)
            result.append({'value': asset.ticker.id,
                           'text': asset.ticker.symbol.upper(),
                           'subtext': '(~ ' + free + ')'}) 

    for asset in stables:
        if asset.id not in ids:
            result.append({'value': asset.id,
                           'text': asset.symbol.upper()}) 

    return json.dumps(result)


@wallet.route('/ajax_currencies', methods=['GET'])
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


@wallet.route('/te', methods=['GET'])
@login_required
def ajax_curren():
    items = db.session.execute(db.select(WalletTransaction).filter_by(wallet_asset_id=None)).scalars()

    for item in items:
        db.session.delete(item)
    db.session.commit()

    return 'Delete'
