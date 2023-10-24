import json
from datetime import datetime
from flask import flash, render_template, session, url_for, request, Blueprint
from flask_babel import gettext
from flask_login import login_required, current_user

from portfolio_tracker.app import db, app
from portfolio_tracker.general_functions import get_price, int_, float_, get_price_list
from portfolio_tracker.models import Alert, Details, Portfolio, Asset, Ticker, OtherAsset, \
        OtherTransaction, OtherBody, Transaction
from portfolio_tracker.wallet.wallet import get_wallet_has_asset, last_wallet, last_wallet_transaction
from portfolio_tracker.watchlist.watchlist import get_watchlist_asset
from portfolio_tracker.wraps import demo_user_change


portfolio = Blueprint('portfolio',
                      __name__,
                      template_folder='templates',
                      static_folder='static')


def get_portfolio(id):
    if id:
        for portfolio in current_user.portfolios:
            if portfolio.id == int(id):
                return portfolio
    return None


def get_asset(portfolio, ticker_id, create=False):
    if portfolio and ticker_id:
        for asset in portfolio.assets:
            if asset.ticker_id == ticker_id:
                return asset
        else:
            if create:
                asset = Asset(ticker_id=ticker_id)
                portfolio.assets.append(asset)
                db.session.commit()
                return asset
    return None


def get_other_asset(portfolio, asset_id):
    if portfolio and asset_id:
        for asset in portfolio.other_assets:
            if asset.id == int(asset_id):
                return asset
    return None


def get_transaction(asset, transaction_id):
    if asset and transaction_id:
        for transaction in asset.transactions:
            if transaction.id == int(transaction_id):
                return transaction
    return None


def get_other_body(asset, body_id):
    if asset and body_id:
        for body in asset.bodies:
            if body.id == int(body_id):
                return body
    return None


class AllPortfolios(Details):
    def __init__(self):
        self.amount = 0
        self.cost_now = 0
        self.in_orders = 0
        for portfolio in current_user.portfolios:
            portfolio.update_price()
            portfolio.update_details()
            self.amount += portfolio.amount
            self.cost_now += portfolio.cost_now
            self.in_orders += portfolio.in_orders
        self.update_details()


@portfolio.route('/', methods=['GET'])
@login_required
def portfolios():
    """ Portfolios page """
    return render_template('portfolio/portfolios.html',
                           all_portfolios=AllPortfolios())


@portfolio.route('/action', methods=['POST'])
@login_required
@demo_user_change
def portfolios_action():
    """ Action portfolio """
    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data['action']

    for id in ids:
        portfolio = get_portfolio(id)
        if not portfolio:
            continue

        if 'delete' in action:
            if 'with_contents' not in action and not portfolio.is_empty():
                flash(gettext('В портфеле %(name)s есть транзакции',
                              name=portfolio.name), 'danger')
            else:
                portfolio.delete()

    db.session.commit()
    return ''


@portfolio.route('/portfolio_settings', methods=['GET'])
@login_required
def portfolio_settings():
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    return render_template('portfolio/portfolio_settings.html',
                            portfolio=portfolio)


@portfolio.route('/portfolio_settings_update', methods=['POST'])
@login_required
@demo_user_change
def portfolio_settings_update():
    """ Add or change portfolio """
    portfolio = get_portfolio(request.args.get('portfolio_id'))

    name = request.form.get('name')
    comment = request.form.get('comment')
    market = request.form.get('market')
    percent = float_(request.form.get('percent'))

    if not portfolio:
        user_portfolios = current_user.portfolios
        names = [i.name for i in user_portfolios if i.market == market]
        if name in names:
            n = 2
            while str(name) + str(n) in names:
                n += 1
            name = str(name) + str(n)
        portfolio = Portfolio(user_id=current_user.id,
                              market=market)
        db.session.add(portfolio)

    if name is not None:
        portfolio.name = name
    portfolio.percent = percent
    portfolio.comment = comment
    db.session.commit()

    return ''


@portfolio.route('/<int:portfolio_id>', methods=['GET'])
@login_required
def portfolio_info(portfolio_id):
    """ Portfolio page """
    portfolio = get_portfolio(portfolio_id)
    if not portfolio:
        return ''
    # portfolio.update_price()
    # portfolio.update_details()

    page = 'other_' if portfolio.market == 'other' else ''
    return render_template('portfolio/' + page + 'portfolio_info.html',
                           portfolio=portfolio,
                           all_portfolios=AllPortfolios())


@portfolio.route('/assets_action', methods=['POST'])
@login_required
@demo_user_change
def assets_action():
    """ Asset action """
    portfolio = get_portfolio(request.args.get('portfolio_id'))

    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data['action']

    for ticker_id in ids:
        asset = get_asset(portfolio, ticker_id)
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


@portfolio.route('/<string:market>/add_asset_modal', methods=['GET'])
@login_required
def asset_add_modal(market):
    return render_template('portfolio/add_asset_modal.html',
                           market=market,
                           portfolio_id=request.args.get('portfolio_id'))


@portfolio.route('/<string:market>/add_asset_tickers', methods=['GET'])
@login_required
def asset_add_tickers(market):
    per_page = 20
    search = request.args.get('search')

    query = (Ticker.query.filter(Ticker.market == market)
        # .order_by(Ticker.id))
        # .order_by(Ticker.market_cap_rank.nulls_last(), Ticker.id))
        .order_by(Ticker.market_cap_rank.is_(None),
                  Ticker.market_cap_rank.asc()))

    if search:
        query = query.filter(Ticker.name.contains(search)
                             | Ticker.symbol.contains(search))

    tickers = query.paginate(page=int_(request.args.get('page'), 1),
                             per_page=per_page,
                             error_out=False)
    if tuple(tickers):
        return render_template('portfolio/add_asset_tickers.html',
                               tickers=tickers)
    return 'end'


@portfolio.route('/add_asset', methods=['GET'])
@login_required
@demo_user_change
def asset_add():
    """ Add asset to portfolio """
    ticker_id = request.args.get('ticker_id')
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(portfolio, ticker_id=ticker_id, create=True)
    if not asset:
        return ''

    return str(url_for('.asset_info',
                portfolio_id=asset.portfolio_id,
                only_content=request.args.get('only_content'),
                ticker_id=asset.ticker_id))


@portfolio.route('/asset_settings', methods=['GET'])
@login_required
def asset_settings():
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(portfolio, request.args.get('ticker_id'))
    return render_template('portfolio/asset_settings.html',
                           asset=asset)


@portfolio.route('/asset_settings_update', methods=['POST'])
@login_required
@demo_user_change
def asset_settings_update():
    """ Change asset """
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(portfolio, request.args.get('ticker_id'))
    if asset:
        comment = request.form.get('comment')
        percent = request.form.get('percent')
        if comment != None:
            asset.comment = comment
        if percent != None:
            asset.percent = percent
        db.session.commit()
    return ''


@portfolio.route('/asset_info')
@login_required
def asset_info():
    """ Asset page """
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    if not portfolio:
        return ''

    if portfolio.market != 'other':
        asset = get_asset(portfolio, request.args.get('ticker_id'))
    else:
        asset = get_other_asset(portfolio, request.args.get('asset_id'))

    if not asset:
        return ''

    asset.portfolio.update_price()
    asset.update_details()

    page = 'other_' if portfolio.market == 'other' else ''
    return render_template('portfolio/' + page + 'asset_info.html',
                           asset=asset)


@portfolio.route('/transaction_action', methods=['POST'])
@login_required
@demo_user_change
def transactions_action():
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(portfolio, request.args.get('ticker_id'))

    data = json.loads(request.data) if request.data else {}
    action = data['action']
    ids = data['ids']

    for id in ids:
        transaction = get_transaction(asset, id)
        if not transaction:
            continue

        if action == 'delete':
            transaction.delete()

        elif action == 'convert_to_transaction':
            transaction.convert_order_to_transaction()

    db.session.commit()
    return ''


@portfolio.route('/transaction', methods=['GET'])
@login_required
def transaction():
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(portfolio, request.args.get('ticker_id'))
    if not asset:
        return ''

    asset.update_price()
    asset.free = asset.get_free()
    transaction = get_transaction(asset, request.args.get('transaction_id'))

    if transaction:
        exec('transaction.wallet_%s = transaction.wallet' % transaction.type.lower())

        if transaction.order and transaction.type == 'Sell':
            asset.free -= transaction.quantity
    else:
        transaction = Transaction(
            type='Buy',
            date=datetime.today().isoformat(sep='T', timespec='minutes'),
            # quote_ticker=quote_ticker,
            price = asset.price
        )
    if not hasattr(transaction, 'wallet_buy'):
        transaction.wallet_buy = last_wallet('buy')
    if not hasattr(transaction, 'wallet_sell'):
        transaction.wallet_sell = get_wallet_has_asset(asset.ticker_id)

    last_transaction = last_wallet_transaction(
        transaction.wallet or transaction.wallet_buy,
        # transaction.wallet if transaction.wallet else transaction.wallet_buy,
        transaction.type
    )
    if last_transaction:
        transaction.quote_ticker = last_transaction.quote_ticker
        transaction.quote_ticker.price = get_price(transaction.quote_ticker.id, 1)

    calculation_type = session.get('transaction_calculation_type', 'amount')

    return render_template('portfolio/transaction.html',
                           transaction=transaction,
                           asset=asset,
                           calculation_type=calculation_type)


@portfolio.route('/transaction_update', methods=['POST'])
@login_required
@demo_user_change
def transaction_update():
    """ Add or change transaction """
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(portfolio, request.args.get('ticker_id'))
    if not asset:
        return ''

    transaction = get_transaction(asset, request.args.get('transaction_id'))
    alert = None
    if transaction:
        transaction.update_dependencies('cancel')
        if transaction.alert:
            alert = transaction.alert
    else:
        transaction = Transaction(portfolio_id=asset.portfolio_id)
        asset.transactions.append(transaction)


    transaction.type = request.form['type']
    type = 1 if transaction.type == 'Buy' else -1
    transaction.date = request.form['date']
    transaction.ticker2_id = request.form['ticker2_id']
    transaction.price = float(request.form['price'])
    transaction.price_usd = transaction.price * get_price(transaction.ticker2_id, 1)
    transaction.comment = request.form['comment']
    transaction.wallet_id = request.form[transaction.type.lower() + '_wallet_id']
    transaction.order = bool(request.form.get('order'))

    if request.form.get('quantity'):
        transaction.quantity = float(request.form['quantity']) * type
        transaction.quantity2 = transaction.price * transaction.quantity * -1
        session['transaction_calculation_type'] = 'quantity'
    else:
        transaction.quantity2 = float(request.form['quantity2']) * type * -1
        transaction.quantity = transaction.quantity2 / transaction.price * -1
        session['transaction_calculation_type'] = 'amount'

    # Уведомление
    if not transaction.order and alert:
        alert.delete()
    elif transaction.order:
        if not alert:
            alert = Alert()
            watchlist_asset = get_watchlist_asset(asset.ticker_id, True)
            if watchlist_asset:
                watchlist_asset.alerts.append(alert)

        alert.price = transaction.price_usd
        alert.price_usd = transaction.price_usd
        alert.price_ticker_id = transaction.ticker2_id
        alert.date = transaction.date
        alert.transaction_id = transaction.id
        alert.asset_id = asset.id
        alert.comment = transaction.comment

        asset_price = get_price(asset.ticker_id, 1)
        alert.type = 'down' if asset_price >= alert.price_usd else 'up'


    db.session.commit()
    transaction.update_dependencies()
    db.session.commit()

    return ''

# Other assets

@portfolio.route('/other_asset_action', methods=['POST'])
@login_required
@demo_user_change
def other_asset_action():
    """ Other assets action """
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id'))

    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data['action']

    for asset_id in ids:
        asset = get_other_asset(portfolio, asset_id)
        if not asset:
            continue

        if 'delete' in action:
            if 'with_contents' not in action and not asset.is_empty():
                flash(gettext('Актив %(name)s не пустой',
                              name=asset.name), 'danger')
            else:
                asset.delete()

    db.session.commit()
    return ''


@portfolio.route('/other_asset/transaction_action', methods=['POST'])
@login_required
def other_transaction_action():
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id'))

    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data['action']

    for transaction_id in ids:
        transaction = get_transaction(asset, transaction_id)
        if not transaction:
            continue

        if action == 'delete':
            db.session.delete(transaction)

    db.session.commit()
    session['other_asset_page'] = 'transactions'
    return ''


@portfolio.route('/other_asset/body_action', methods=['POST'])
@login_required
def other_body_action():
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id'))

    data = json.loads(request.data) if request.data else {}
    action = data['action']
    ids = data['ids']

    for body_id in ids:
        body = get_other_body(asset, body_id)
        if not body:
            continue

        if action == 'delete':
            db.session.delete(body)

    db.session.commit()
    session['other_asset_page'] = 'bodies'
    return ''


@portfolio.route('/<int:portfolio_id>/other_asset_settings', methods=['GET'])
@login_required
def other_asset_settings(portfolio_id):
    portfolio = get_portfolio(portfolio_id)
    asset = get_other_asset(portfolio, request.args.get('asset_id'))
    return render_template('portfolio/other_asset_settings.html',
                           asset=asset,
                           portfolio_id=portfolio_id)


@portfolio.route('/<int:portfolio_id>/other_asset_update', methods=['POST'])
@login_required
@demo_user_change
def other_asset_settings_update(portfolio_id):
    """ Add other asset to portfolio """
    portfolio = get_portfolio(portfolio_id)
    asset = get_other_asset(portfolio, request.args.get('asset_id'))
    if not asset:
        asset = OtherAsset(portfolio_id=portfolio_id)
        db.session.add(asset)

    name = request.form.get('name')

    if asset.name != name:
        n = 2
        while name in [i.name for i in portfolio.other_assets]:
            name = request.form['name'] + str(n)
            n += 1

    asset.name = name
    comment = request.form.get('comment')
    percent = request.form.get('percent')
    if comment != None:
        asset.comment = comment
    if percent != None:
        asset.percent = float_(percent, 0)

    db.session.commit()
    return ''


@portfolio.route('/other_asset_transaction', methods=['GET'])
@login_required
def other_transaction():
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id'))
    if not asset:
        return ''

    transaction = get_transaction(asset, request.args.get('transaction_id'))

    return render_template('portfolio/other_transaction.html',
                           asset=asset,
                           date=datetime.now().date(),
                           transaction=transaction)


@portfolio.route('/other_asset_transaction_update', methods=['POST'])
@login_required
@demo_user_change
def other_transaction_update():
    """ Add or change transaction of other asset """
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id'))
    if not asset:
        return ''

    transaction = get_transaction(asset, request.args.get('transaction_id'))
    if transaction:
        transaction.update_dependencies('cancel')
    else:
        transaction = OtherTransaction()
        asset.transactions.append(transaction)

    price_list = get_price_list()
    transaction.type = request.form['type']
    type = 1 if transaction.type == 'Profit' else -1
    transaction.amount_ticker_id = request.form['amount_ticker_id']
    transaction.amount_with_ticker = float(request.form['amount']) * type
    transaction.amount = (transaction.amount_with_ticker
                          / price_list.get(transaction.amount_ticker_id))
    transaction.comment = request.form['comment']
    transaction.date = request.form['date']

    db.session.commit()
    transaction.update_dependencies()
    db.session.commit()
    session['other_asset_page'] = 'transactions'
    
    return ''


@portfolio.route('/other_asset_body', methods=['GET'])
@login_required
def other_body():
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id'))
    body = get_other_body(asset, request.args.get('body_id'))

    return render_template('portfolio/other_body.html',
                           asset=asset,
                           date=datetime.now().date(),
                           body=body)


@portfolio.route('/other_asset_body_update', methods=['POST'])
@login_required
@demo_user_change
def other_body_update():
    """ Add or change body of other asset """
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id'))
    if not asset:
        return ''

    body = get_other_body(asset, request.args.get('body_id'))
    if body:
        body.update_dependencies('cancel')
    else:
        body = OtherBody(asset_id=asset.id)
        db.session.add(body)

    price_list = get_price_list()
    body.name = request.form['name']
    body.amount_ticker_id = request.form['amount_ticker_id']
    body.amount_with_ticker = float(request.form['amount'])
    body.amount = body.amount_with_ticker / price_list.get(body.amount_ticker_id, 1)
    body.cost_now_with_ticker = float(request.form['cost_now'])
    body.cost_now = body.cost_now_with_ticker / price_list.get(body.amount_ticker_id, 1)
    body.comment = request.form['comment']
    body.date = request.form['date']

    db.session.commit()
    body.update_dependencies()
    db.session.commit()
    session['other_asset_page'] = 'bodies'
    return ''


@portfolio.route('/change_table_sort', methods=['GET'])
@login_required
def change_table_sort():
    tab_name = request.args.get('tab_name')
    field = request.args.get('field')
    sort_order = request.args.get('sort_order')

    session[tab_name] = {'field': field, 'sort_order': sort_order}
    return ''


@portfolio.route('/ajax_stable', methods=['GET'])
@login_required
def ajax_stable_assets():
    result = []
    tickers = db.session.execute(db.select(Ticker).filter_by(stable=True)).scalars()
    for ticker in tickers:
        result.append({'value': ticker.id,
                       'text': ticker.symbol.upper()}) 
    else:
        result = {'message': 'Нет тикеров'}

    return json.dumps(result)


