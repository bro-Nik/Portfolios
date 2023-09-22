import json
from datetime import datetime
from flask import flash, render_template, redirect, session, url_for, request, Blueprint
from flask_babel import gettext
from flask_login import login_required, current_user

from portfolio_tracker.app import db
from portfolio_tracker.general_functions import int_, float_, get_price_list
from portfolio_tracker.jinja_filters import number_group, smart_round
from portfolio_tracker.models import Portfolio, Asset, Ticker, OtherAsset, \
        OtherTransaction, OtherBody, Transaction, Alert
from portfolio_tracker.whitelist.whitelist import get_whitelist_ticker
from portfolio_tracker.wraps import demo_user_change


portfolio = Blueprint('portfolio',
                      __name__,
                      template_folder='templates',
                      static_folder='static')


def get_portfolio(id):
    if id:
        return db.session.execute(
            db.select(Portfolio).filter_by(id=id,
                                           user_id=current_user.id)).scalar()
    return None


def get_asset(id):
    if id:
        asset = db.session.execute(
            db.select(Asset).filter_by(id=id)).scalar()
        if asset and asset.portfolio.user_id == current_user.id:
            return asset
    return None


def get_other_asset(id):
    if id:
        asset = db.session.execute(
            db.select(OtherAsset).filter_by(id=id)).scalar()
        if asset and asset.portfolio.user_id == current_user.id:
            return asset
    return None


def get_transaction(id):
    if id:
        transaction = db.session.execute(
            db.select(Transaction).filter_by(id=id)).scalar()
        if transaction and transaction.asset.portfolio.user_id == current_user.id:
            return transaction
    return None


def get_other_transaction(id):
    if id:
        transaction = db.session.execute(
                db.select(OtherTransaction).filter_by(id=id)).scalar()
        if transaction and  transaction.asset.portfolio.user_id == current_user.id:
            return transaction
    return None


def get_other_body(id):
    if id:
        body = db.session.execute(
                db.select(OtherBody).filter_by(id=id)).scalar()
        if body and body.asset.portfolio.user_id == current_user.id:
            return body
    return None


def get_ticker(id):
    if not id:
        return None
    return db.session.execute(db.select(Ticker).filter_by(id=id)).scalar()


def delete_asset(asset):
    if asset:
        for transaction in asset.transactions:
            delete_transaction(transaction)

        for alert in asset.alerts:
            # отставляем уведомления
            alert.asset_id = None
            alert.comment = gettext('Portfolio %(name)s deleted',
                                    name=asset.portfolio.name)

        db.session.delete(asset)


def delete_transaction(transaction):
    if transaction.order:
        # Мистика
        if transaction.alert:
            db.session.delete(transaction.alert[0])
    db.session.delete(transaction)


class AllPortfolios:
    def __init__(self):
        price_list = get_price_list()
        self.total_spent = 0
        self.cost_now = 0
        self.in_orders = 0
        for portfolio in current_user.portfolios:
            portfolio.update_details(price_list)
            self.total_spent += portfolio.total_spent
            self.cost_now += portfolio.cost_now
            self.in_orders += portfolio.in_orders

        self.profit = int(self.cost_now - self.total_spent)
        if self.profit > 0:
            self.color = 'text-green'
        elif self.profit < 0:
            self.color = 'text-red'

        if self.profit and self.total_spent:
            self.profit_percent = abs(int(self.profit / self.total_spent * 100))
        self.total_spent = int(self.total_spent)
        self.cost_now = int(self.cost_now)
        self.in_orders = int(self.in_orders)


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
                flash(gettext('There are transactions in the %(name)s portfolio',
                              name=portfolio.name), 'danger')
            else:
                for asset in portfolio.assets:
                    delete_asset(asset)

                db.session.delete(portfolio)

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
    name = request.form.get('name')
    comment = request.form.get('comment')
    market_id = request.form.get('market_id')
    percent = float_(request.form.get('percent'))

    portfolio = get_portfolio(request.args.get('portfolio_id'))

    if not portfolio:
        user_portfolios = current_user.portfolios
        names = [i.name for i in user_portfolios if i.market_id == market_id]
        if name in names:
            n = 2
            while str(name) + str(n) in names:
                n += 1
            name = str(name) + str(n)
        portfolio = Portfolio(user_id=current_user.id,
                              market_id=market_id)
        db.session.add(portfolio)

    if name is not None:
        portfolio.name = name
    portfolio.percent = percent
    portfolio.comment = comment
    db.session.commit()

    return ''


@portfolio.route('/portfolio/<int:portfolio_id>', methods=['GET'])
@login_required
def portfolio_info(portfolio_id):
    """ Portfolio page """
    portfolio = get_portfolio(portfolio_id)
    if not portfolio:
        return ''

    page = 'other_' if portfolio.market_id == 'other' else ''
    return render_template('portfolio/' + page + 'portfolio_info.html',
                           portfolio=portfolio,
                           all_portfolios=AllPortfolios())


@portfolio.route('/assets_action', methods=['POST'])
@login_required
@demo_user_change
def assets_action():
    """ Asset action """
    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data['action']

    for id in ids:
        asset = get_asset(id)
        if not asset:
            continue

        if 'delete' in action:
            if 'with_contents' not in action and not asset.is_empty():
                flash(gettext('There are transactions in the %(name)s asset',
                              name=asset.ticker.name), 'danger')
            else:
                delete_asset(asset)

    db.session.commit()
    return ''


@portfolio.route('/<string:market_id>/add_asset_modal', methods=['GET'])
@login_required
def asset_add_modal(market_id):
    return render_template('portfolio/add_asset_modal.html',
                           market_id=market_id,
                           portfolio_id=request.args.get('portfolio_id'))


@portfolio.route('/<string:market_id>/add_asset_tickers', methods=['GET'])
@login_required
def asset_add_tickers(market_id):
    per_page = 20
    search = request.args.get('search')

    query = (Ticker.query.filter(Ticker.market_id == market_id)
        .order_by(Ticker.market_cap_rank.nulls_last(), Ticker.id))

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


@portfolio.route('/<int:portfolio_id>/add_asset', methods=['GET'])
@login_required
@demo_user_change
def asset_add(portfolio_id):
    """ Add asset to portfolio """
    ticker_id = request.args.get('ticker_id')
    portfolio = get_portfolio(portfolio_id)
    if not portfolio:
        return ''

    asset = None
    for asset_in_portfolio in portfolio.assets:
        if asset_in_portfolio.ticker_id == ticker_id:
            asset = asset_in_portfolio
            break

    if not asset:
        asset = Asset(ticker_id=ticker_id,
                      portfolio_id=portfolio.id)
        db.session.add(asset)
        db.session.commit()

    return str(url_for('.asset_info',
                market_id=portfolio.market_id,
                only_content=request.args.get('only_content'),
                asset_id=asset.id))


@portfolio.route('/asset_settings', methods=['GET'])
@login_required
def asset_settings():
    asset = get_asset(request.args.get('asset_id'))
    return render_template('portfolio/asset_settings.html',
                           asset=asset)


@portfolio.route('/asset_settings_update', methods=['POST'])
@login_required
@demo_user_change
def asset_settings_update():
    """ Change asset """
    asset = get_asset(request.args.get('asset_id'))
    if asset:
        comment = request.form.get('comment')
        percent = request.form.get('percent')
        if comment != None:
            asset.comment = comment
        if percent != None:
            asset.percent = percent
        db.session.commit()
    return ''


@portfolio.route('/<string:market_id>/asset_<int:asset_id>')
@login_required
def asset_info(market_id, asset_id):
    """ Asset page """
    if market_id != 'other':
        asset = get_asset(asset_id)
    else:
        asset = get_other_asset(asset_id)

    if not asset:
        return ''

    price_list = get_price_list()
    # asset.update_details(price_list)
    asset.portfolio.update_details(price_list)

    page = 'other_' if market_id == 'other' else ''
    return render_template('portfolio/' + page + 'asset_info.html',
                           asset=asset)


@portfolio.route('/asset_info/<string:asset_id>')
@login_required
def asset_detail(asset_id):
    asset = get_asset(asset_id)
    if not asset:
        return ''

    asset.update_details(get_price_list())

    alerts = []
    for alert in asset.alerts:
        if alert.status != 'off':
            alerts.append({'price': number_group(smart_round(alert.price)),
                           'status': alert.status})

    if asset.profit_percent:
        asset.profit_percent = ' (' + str(int(abs(asset.profit_percent))) + '%)'

    profit = '$0' 
    if asset.profit > 0:
        profit = '+$' + str(number_group(asset.profit))
    elif asset.profit < 0:
        profit = '-$' + str(number_group(abs(asset.profit)))

    return {
        "price": number_group(smart_round(asset.price)) if asset.price else '-',
        "cost_now": '$' + str(number_group(asset.cost_now)),
        "profit": profit + asset.profit_percent,
        "color": asset.color,
        "alerts": alerts
    }


@portfolio.route('/transaction_action', methods=['POST'])
@login_required
@demo_user_change
def transactions_action():
    data = json.loads(request.data) if request.data else {}
    action = data['action']
    ids = data['ids']

    for id in ids:
        transaction = get_transaction(id)
        if not transaction:
            continue

        if action == 'delete':
            delete_transaction(transaction)

        elif action == 'convert_to_transaction':
            transaction.order = 0
            transaction.date = datetime.now().date()

    db.session.commit()
    return ''


@portfolio.route('/<int:asset_id>/transaction', methods=['GET'])
@login_required
def transaction(asset_id):
    transaction = get_transaction(request.args.get('transaction_id'))

    return render_template('portfolio/transaction.html',
                           transaction=transaction,
                           date=datetime.now().date(),
                           asset_id=asset_id,
                           price=request.args.get('price'))


@portfolio.route('/<int:asset_id>/transaction_update', methods=['POST'])
@login_required
@demo_user_change
def transaction_update(asset_id):
    """ Add or change transaction """
    asset = get_asset(asset_id)
    if not asset:
        return ''

    transaction = get_transaction(request.args.get('transaction_id'))
    if not transaction:
        transaction = Transaction(asset_id=asset_id)
        db.session.add(transaction)

    transaction.price = float(request.form['price'])
    transaction.total_spent = float(request.form['total_spent'])
    transaction.type = request.form['type']
    transaction.comment = request.form['comment']
    transaction.date = request.form['date']
    transaction.order = bool(request.form.get('order'))
    transaction.wallet_id = request.form['wallet_id']
    transaction.quantity = transaction.total_spent / transaction.price

    if transaction.type == '-':
        transaction.quantity *= -1
        transaction.total_spent *= -1

    if transaction.order and not transaction.alert:
        # Добавляем уведомление
        whitelist_ticker = get_whitelist_ticker(asset.ticker_id, True)
        price_list = get_price_list(asset.ticker.market_id)
        cost_now = float_(price_list.get(asset.ticker_id), 0)

        alert = Alert(
            price=transaction.price,
            date=transaction.date,
            comment=transaction.comment,
            transaction_id=transaction.id,
            asset_id=asset_id,
            whitelist_ticker_id=whitelist_ticker.id,
            type='down' if cost_now >= transaction.price else 'up'
        )
        db.session.add(alert)

    db.session.commit()
    return ''

# Other assets

@portfolio.route('/other_asset_action', methods=['POST'])
@login_required
@demo_user_change
def other_asset_action():
    """ Other assets action """
    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data['action']

    for id in ids:
        asset = get_other_asset(id)
        if not asset:
            continue

        if 'delete' in action:
            if 'with_contents' not in action and not asset.is_empty():
                flash(gettext('Asset %(name)s is not empty',
                              name=asset.name), 'danger')
            else:
                for body in asset.bodies:
                    db.session.delete(body)
                for transaction in asset.transactions:
                    db.session.delete(transaction)
                db.session.delete(asset)

    db.session.commit()
    return ''


@portfolio.route('/other_asset/transaction_action', methods=['POST'])
@login_required
def other_transaction_action():
    data = json.loads(request.data) if request.data else {}
    ids = data['ids']
    action = data['action']

    for id in ids:
        transaction = get_other_transaction(id)
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
    data = json.loads(request.data) if request.data else {}

    action = data['action']
    ids = data['ids']

    for id in ids:
        body = get_other_body(id)
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
    asset = get_other_asset(request.args.get('asset_id'))
    return render_template('portfolio/other_asset_settings.html',
                           asset=asset,
                           portfolio_id=portfolio_id)


@portfolio.route('/<int:portfolio_id>/other_asset_update', methods=['POST'])
@login_required
@demo_user_change
def other_asset_settings_update(portfolio_id):
    """ Add other asset to portfolio """
    asset = get_other_asset(request.args.get('asset_id'))
    if not asset:
        asset = OtherAsset(portfolio_id=portfolio_id)
        db.session.add(asset)

    name = request.form.get('name')

    if asset.name != name:
        portfolio = get_portfolio(portfolio_id)
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
        asset.percent = percent

    db.session.commit()
    return ''


@portfolio.route('/other_asset_<int:asset_id>/transaction', methods=['GET'])
@login_required
def other_transaction(asset_id):
    transaction = get_other_transaction(request.args.get('transaction_id'))

    return render_template('portfolio/other_transaction.html',
                           asset_id=asset_id,
                           date=datetime.now().date(),
                           transaction=transaction)


@portfolio.route('/other_asset_<int:asset_id>/transaction_update', methods=['POST'])
@login_required
@demo_user_change
def other_transaction_update(asset_id):
    """ Add or change transaction of other asset """
    transaction = get_other_transaction(request.args.get('transaction_id'))
    if not transaction:
        transaction = OtherTransaction(asset_id=asset_id)
        db.session.add(transaction)

    total_spent = request.form['total_spent']
    transaction.type = request.form['type']
    transaction.total_spent = float(transaction.type + total_spent)
    transaction.comment = request.form['comment']
    transaction.date = request.form['date']

    db.session.commit()
    session['other_asset_page'] = 'transactions'
    return ''


@portfolio.route('/other_asset_<int:asset_id>/body', methods=['GET'])
@login_required
def other_body(asset_id):
    body = get_other_body(request.args.get('body_id'))

    return render_template('portfolio/other_body.html',
                           asset_id=asset_id,
                           date=datetime.now().date(),
                           body=body)


@portfolio.route('/other_asset_<int:asset_id>/body_update', methods=['POST'])
@login_required
@demo_user_change
def other_body_update(asset_id):
    """ Add or change body of other asset """
    body = get_other_body(request.args.get('body_id'))
    if not body:
        body = OtherBody(asset_id=asset_id)
        db.session.add(body)

    body.name = request.form['name']
    body.total_spent = float(request.form['total_spent'])
    body.cost_now = float(request.form['cost_now'])
    body.comment = request.form['comment']
    body.date = request.form['date']

    db.session.commit()
    session['other_asset_page'] = 'bodies'
    return ''
