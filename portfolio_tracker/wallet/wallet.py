import json
from datetime import datetime
from flask import flash, render_template, request, Blueprint, url_for
from flask_babel import gettext
from flask_login import login_required, current_user
from portfolio_tracker.app import db
from portfolio_tracker.general_functions import get_price, int_
from portfolio_tracker.jinja_filters import other_currency, user_currency
from portfolio_tracker.models import Ticker, Transaction, Wallet, WalletAsset
from portfolio_tracker.user.user import create_first_wallet
from portfolio_tracker.wraps import demo_user_change


wallet = Blueprint('wallet',
                   __name__,
                   template_folder='templates',
                   static_folder='static')


def get_wallet(wallet_id):
    if wallet_id:
        for wallet in current_user.wallets:
            if wallet.id == int(wallet_id):
                return wallet
    return None


def get_wallet_has_asset(ticker_id):
    for wallet in current_user.wallets:
        asset = get_wallet_asset(wallet, ticker_id)
        if asset:
            asset.update_price()
            if asset.free > 0:
                return wallet
    return None


def get_wallet_asset(wallet, ticker_id, create=False):
    if wallet and ticker_id:
        for asset in wallet.wallet_assets:
            if asset.ticker_id == ticker_id:
                return asset
        else:
            if create:
                asset = WalletAsset(ticker_id=ticker_id)
                wallet.wallet_assets.append(asset)
                db.session.commit()
                return asset
    return None


def get_transaction(asset, transaction_id):
    if transaction_id and asset:
        for transaction in asset.transactions:
            if transaction.id == int(transaction_id):
                return transaction
    return None


class AllWallets:
    def __init__(self):
        self.cost_now = 0
        self.in_orders = 0
        self.free = 0

        for wallet in current_user.wallets:
            wallet.update_price()
            self.cost_now += wallet.cost_now
            self.in_orders += wallet.in_orders
            self.free += wallet.free


@wallet.route('', methods=['GET'])
@login_required
def wallets():
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
                flash(gettext('Кошелек %(name)s не пустой',
                               name=wallet.name), 'danger')
            else:
                wallet.delete()

    db.session.commit()
    if not current_user.wallets:
        create_first_wallet(current_user)
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
    name = request.form.get('name')
    wallet = get_wallet(request.args.get('wallet_id'))

    if not wallet:
        user_wallets = current_user.wallets
        names = [i.name for i in user_wallets]
        if name in names:
            n = 2
            while str(name) + str(n) in names:
                n += 1
            name = str(name) + str(n)
        wallet = Wallet(user_id=current_user.id)
        db.session.add(wallet)

    if name is not None:
        wallet.name = name
    wallet.comment = request.form.get('comment')

    db.session.commit()
    return ''


@wallet.route('/wallet_info', methods=['GET'])
@login_required
def wallet_info():
    """ Wallet page """
    wallet = get_wallet(request.args.get('wallet_id'))
    if not wallet:
        return ''

    wallet.update_price()
    return render_template('wallet/wallet_info.html', wallet=wallet)


@wallet.route('/assets_action', methods=['POST'])
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


@wallet.route('/asset_info', methods=['GET'])
@login_required
def asset_info():
    wallet = get_wallet(request.args.get('wallet_id'))
    asset = get_wallet_asset(wallet, request.args.get('ticker_id'))
    if not asset:
        return ''

    asset.update_price()

    page = 'stable_' if asset.ticker.stable else ''
    return render_template('wallet/' + page + 'asset_info.html', asset=asset)


@wallet.route('/add_stable_modal', methods=['GET'])
@login_required
def stable_add_modal():
    return render_template('wallet/add_stable_modal.html',
                           wallet_id=request.args.get('wallet_id'))


@wallet.route('/add_stable_tickers', methods=['GET'])
@login_required
def stable_add_tickers():
    per_page = 20
    search = request.args.get('search')

    query = (Ticker.query.filter(Ticker.stable == True)
        .order_by(Ticker.id))
        # .order_by(Ticker.market_cap_rank.nulls_last(), Ticker.id))

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


@wallet.route('/add_stable', methods=['GET'])
@login_required
def stable_add():
    wallet = get_wallet(request.args.get('wallet_id'))
    asset = get_wallet_asset(wallet, request.args.get('ticker_id'), create=True)
    if not asset:
        return ''

    return str(url_for('.asset_info',
                       wallet_id=asset.wallet_id,
                       ticker_id=asset.ticker_id,
                       only_content=request.args.get('only_content')))


@wallet.route('/transaction', methods=['GET'])
@login_required
def transaction():
    wallet = get_wallet(request.args.get('wallet_id'))
    asset = get_wallet_asset(wallet, request.args.get('ticker_id'))
    if not asset:
        return ''

    asset.update_price()
    transaction = get_transaction(asset, request.args.get('transaction_id'))
    if not transaction:
        transaction = Transaction(
            type='Input' if asset.ticker.stable else 'TransferOut',
            date=datetime.today().isoformat(sep='T', timespec='minutes')
        )
    return render_template('wallet/transaction.html',
                           asset=asset,
                           transaction=transaction)


@wallet.route('/transaction_update', methods=['POST'])
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
        transaction = Transaction(ticker_id=asset.ticker_id)
        wallet.transactions.append(transaction)

    transaction.type = request.form['type']
    type = 1 if 'In' in transaction.type else -1
    transaction.date = datetime.strptime(request.form['date'], '%Y-%m-%d')
    transaction.quantity = float(request.form['quantity']) * type
    db.session.commit()
    transaction.update_dependencies()

    # Связанная транзакция
    wallet2 = get_wallet(request.form.get('wallet_id'))
    get_wallet_asset(wallet2, asset.ticker_id, create=True)

    if wallet2:
        if not transaction2:
            transaction2 = Transaction(ticker_id=asset.ticker_id)
            db.session.add(transaction2)

        transaction2.wallet_id = wallet2.id
        transaction2.type = 'TransferOut' if type == 1 else 'TransferIn'
        transaction2.date = transaction.date
        transaction2.quantity = transaction.quantity * -1
        db.session.commit()
        transaction2.update_dependencies()

        transaction.related_transaction_id = transaction2.id
        transaction2.related_transaction_id = transaction.id

    db.session.commit()
    return ''


@wallet.route('/transactions_action', methods=['POST'])
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


@wallet.route('/ajax_wallets_to_sell', methods=['GET'])
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
                               'subtext': '(' + quantity + ')'}) 


    if result:
        result = sorted(result,
                        key=lambda wallet: wallet.get('sort'), reverse=True)
    else:
        result = {'message': gettext('В кошельках нет свободных остатков')}

    return json.dumps(result)


@wallet.route('/ajax_wallets_to_buy', methods=['GET'])
@login_required
def get_wallets_to_buy():
    result = []

    for wallet in current_user.wallets:
        wallet.update_price()

        result.append({'value': str(wallet.id),
                       'text': wallet.name,
                       'sort': wallet.free,
                       'subtext': '(~ ' + user_currency(wallet.free, 'big') + ')'})

    result = sorted(result,
                    key=lambda wallet: wallet.get('sort'), reverse=True)

    return json.dumps(result)


@wallet.route('/ajax_wallets_to_transfer_out', methods=['GET'])
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
        walet_info = {'value': str(wallet.id), 'text': wallet.name, 'sort': sort}
        if sort > 0:
            walet_info['subtext'] = '(' + str(quantity) + ')'
        result.append(walet_info)

    if result:
        result = sorted(result,
                        key=lambda wallet: wallet.get('sort'), reverse=True)

    return json.dumps(result)


@wallet.route('/ajax_wallet_stable_assets', methods=['GET'])
@login_required
def ajax_wallet_stable_assets():
    result = []
    wallet = get_wallet(request.args.get('wallet_id'))
    last_type = request.args.get('last')

    if last_type:
        last_transaction = last_wallet_transaction(wallet, last_type)
        if last_transaction:
            ticker = last_transaction.quote_ticker
            result = {'value': ticker.id,
                      'text': ticker.symbol.upper(),
                      'info': get_price(ticker.id)}
        return json.dumps(result)

    if wallet:
        wallet.update_price()
        stables = wallet.stable_assets
        stables = sorted(stables, key=lambda asset: asset.free, reverse=True)
        for asset in stables:
            result.append({'value': asset.ticker.id,
                           'text': asset.ticker.symbol.upper(),
                           'subtext': '(~ ' + str(int(asset.free)) + ')',
                           'info': get_price(asset.ticker_id)}) 

    if not result:
        result = {'message': gettext('Нет активов в кошельке')}

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


def last_wallet(transaction_type):
    date = wallet = None

    for wallet in current_user.wallets:
        transaction = last_wallet_transaction(wallet, transaction_type)
        if transaction:
            if not date or date < transaction.date:
                date = transaction.date
                wallet = wallet
    return wallet


def last_wallet_transaction(wallet, transaction_type):
    for transaction in wallet.transactions:
        if transaction.type.lower() == transaction_type.lower():
            return transaction
    return None
