import json
from datetime import datetime
from flask import flash, render_template, redirect, url_for, request, Blueprint
from flask_login import login_required, current_user

from portfolio_tracker.app import db
from portfolio_tracker.general_functions import int_or_other, \
        float_or_other, get_ticker, get_price_list
from portfolio_tracker.jinja_filters import number_group, smart_round
from portfolio_tracker.models import Portfolio, Asset, Ticker, otherAsset, \
        otherAssetOperation, otherAssetBody, Transaction, Alert
from portfolio_tracker.whitelist.whitelist import get_whitelist_ticker
from portfolio_tracker.wraps import demo_user_change


portfolio = Blueprint('portfolio',
                      __name__,
                      template_folder='templates',
                      static_folder='static')


def get_user_portfolio(id):
    if id:
        return db.session.execute(
            db.select(Portfolio).filter_by(id=id,
                                           user_id=current_user.id)).scalar()
    return None


def get_user_asset(id):
    if id:
        asset = db.session.execute(
            db.select(Asset).filter_by(id=id)).scalar()
        if asset and asset.portfolio.user_id == current_user.id:
            return asset
    return None


def get_user_other_asset(id):
    if id:
        asset = db.session.execute(
            db.select(otherAsset).filter_by(id=id)).scalar()
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


def get_operation(id):
    if id:
        operation = db.session.execute(
                db.select(otherAssetOperation).filter_by(id=id)).scalar()
        if operation and  operation.asset.portfolio.user_id == current_user.id:
            return operation
    return None


def get_body(id):
    if id:
        body = db.session.execute(
                db.select(otherAssetBody).filter_by(id=id)).scalar()
        if body and body.asset.portfolio.user_id == current_user.id:
            return body
    return None


@portfolio.route('/', methods=['GET'])
@login_required
@demo_user_change
def portfolios():
    """ Portfolios page """
    price_list = get_price_list()
    all = {'total_spent': 0, 'cost_now': 0}
    portfolio_list = []

    for user_portfolio in current_user.portfolios:
        portfolio = {'name': user_portfolio.name,
                     'id': user_portfolio.id,
                     'market': user_portfolio.market.name,
                     'comment': user_portfolio.comment,
                     'total_spent': 0,
                     'cost_now': 0,
                     'can_delete': True}

        # Assets
        if user_portfolio.market_id != 'other':
            price_list_local = price_list[user_portfolio.market_id]
            for asset in user_portfolio.assets:
                price = float_or_other(price_list_local.get(asset.ticker_id), 0)

                for transaction in asset.transactions:
                    portfolio['can_delete'] = False

                    if not price or transaction.order:
                        continue

                    portfolio['total_spent'] += transaction.total_spent
                    portfolio['cost_now'] += transaction.quantity * price

        # Other Assets
        else:
            for asset in user_portfolio.other_assets:

                for body in asset.bodys:
                    portfolio['total_spent'] += body.total_spent
                    portfolio['cost_now'] += body.cost_now

                for operation in asset.operations:
                    portfolio['cost_now'] += operation.total_spent

        portfolio['profit'] = portfolio['cost_now'] - portfolio['total_spent']
        all['total_spent'] += portfolio['total_spent']
        all['cost_now'] += portfolio['cost_now']
        portfolio_list.append(portfolio)

    all['profit'] = all['cost_now'] - all['total_spent']

    return render_template('portfolio/portfolios.html',
                           all=all,
                           portfolio_list=portfolio_list)


@portfolio.route('/action', methods=['POST'])
@login_required
@demo_user_change
def portfolios_action():
    """ Action portfolio """
    data = json.loads(request.data) if request.data else {}

    #action = data.get('action')
    ids = data['ids']

    for portfolio in current_user.portfolios:
        if str(portfolio.id) not in ids:
            continue

        portfolio_has_transactions = False
        for asset in portfolio.assets:
            if asset.transactions:
                portfolio_has_transactions = True
                break

            for alert in asset.alerts:
                # отставляем уведомления
                alert.asset_id = None
                alert.comment = ('Портфель ' + str(asset.portfolio.name)
                                             + ' удален')

        if portfolio_has_transactions:
            flash('В портфеле ' + portfolio.name + ' есть транзакции', 'danger')
            continue
        db.session.delete(portfolio)

    db.session.commit()
    return ''


@portfolio.route('/portfolio_settings', methods=['GET'])
@login_required
@demo_user_change
def portfolio_settings():
    portfolio = get_user_portfolio(request.args.get('portfolio_id'))
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

    portfolio = get_user_portfolio(request.args.get('portfolio_id'))

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
    portfolio.comment = comment
    db.session.commit()

    return ''


@portfolio.route('/portfolio/<int:portfolio_id>', methods=['GET'])
@login_required
@demo_user_change
def portfolio_info(portfolio_id):
    """ Portfolio page """
    user_portfolio = get_user_portfolio(portfolio_id)
    if not user_portfolio:
        return redirect(url_for('.portfolios'))

    portfolio = {'name': user_portfolio.name,
                 'id': user_portfolio.id,
                 'market_id': user_portfolio.market_id,
                 'comment': user_portfolio.comment,
                 'cost_now': 0,
                 'total_spent': 0}

    # crypto or stocks
    price_list = get_price_list(user_portfolio.market_id)

    if user_portfolio.market_id != 'other':

        asset_list = []
        for asset in user_portfolio.assets:
            a = {'id': asset.id,
                 'name': asset.ticker.name,
                 'comment': asset.comment,
                 'symbol': asset.ticker.symbol,
                 'price': float_or_other(price_list.get(asset.ticker.id), 0),
                 'quantity': 0,
                 'total_spent': 0,
                 'percent': asset.percent,
                 'can_delete': False if asset.transactions else True}

            if asset.ticker.image:
                a['image'] = asset.ticker.image

            for transaction in asset.transactions:
                a['quantity'] += transaction.quantity
                a['total_spent'] += transaction.total_spent
            a['cost_now'] = a['quantity'] * a['price']
            a['profit'] = a['cost_now'] - a['total_spent']

            portfolio['cost_now'] += a['quantity'] * a['price']
            portfolio['total_spent'] += a['total_spent']
            asset_list.append(a)

        portfolio['profit'] = portfolio['cost_now'] - portfolio['total_spent']

        return render_template('portfolio/portfolio_info.html',
                               portfolio=portfolio,
                               asset_list=asset_list)
    # other assets
    else:
        asset_list = []
        for asset in user_portfolio.other_assets:
            a = {'id': asset.id,
                 'name': asset.name,
                 'comment': asset.comment,
                 'bodys_cost_now': 0,
                 'bodys_total_spent': 0,
                 'operations_total_spent': 0,
                 'percent': asset.percent}

            for body in asset.bodys:
                a['bodys_total_spent'] += body.total_spent
                a['bodys_cost_now'] += body.cost_now
                portfolio['total_spent'] += body.total_spent
                portfolio['cost_now'] += body.cost_now

            for operation in asset.operations:
                a['operations_total_spent'] += operation.total_spent
                portfolio['cost_now'] += operation.total_spent

            a['profit'] = a['bodys_cost_now'] - a['bodys_total_spent']
            a['profit'] += a['operations_total_spent']
            asset_list.append(a)

        portfolio['profit'] = portfolio['cost_now'] - portfolio['total_spent']

        return render_template('portfolio/other_portfolio_info.html',
                               portfolio=portfolio,
                               asset_list=asset_list)


@portfolio.route('/assets_action', methods=['POST'])
@login_required
@demo_user_change
def assets_action():
    """ Asset action """
    data = json.loads(request.data) if request.data else {}

    # action = data.get('action')
    ids = data.get('ids')

    for id in ids:
        asset = get_user_asset(id)
        if not asset:
            continue

        for transaction in asset.transactions:
            db.session.delete(transaction)

        for alert in asset.alerts:
            # оставляем уведомления
            alert.asset_id = None
            alert.comment = ('Актив удален из портфеля '
                             + str(asset.portfolio.name))

        db.session.delete(asset)
    db.session.commit()

    return ''


@portfolio.route('/<string:market_id>/add_asset_modal', methods=['GET'])
@login_required
@demo_user_change
def asset_add_modal(market_id):

    return render_template('portfolio/add_asset_modal.html',
                           market_id=market_id)


@portfolio.route('/<string:market_id>/add_asset_tickers', methods=['GET'])
@login_required
@demo_user_change
def asset_add_tickers(market_id):
    per_page = 20
    search = request.args.get('search')

    query = (Ticker.query.filter(Ticker.market_id == market_id)
        .order_by(Ticker.market_cap_rank))

    if search:
        query = query.filter(Ticker.name.contains(search)
                             | Ticker.symbol.contains(search))

    
    tickers = query.paginate(page=int_or_other(request.args.get('page'), 1),
                             per_page=per_page,
                             error_out=False)
    if tuple(tickers):
        return render_template('portfolio/add_asset_tickers.html',
                               tickers=tickers)
    else:
        return 'end'



@portfolio.route('/<int:portfolio_id>/add_asset', methods=['GET'])
@login_required
@demo_user_change
def asset_add(portfolio_id):
    """ Add asset to portfolio """
    ticker = get_ticker(request.args.get('ticker_id'))
    portfolio = get_user_portfolio(portfolio_id)
    if not ticker or not portfolio:
        return ''

    asset = None
    for asset_in_portfolio in portfolio.assets:
        if asset_in_portfolio.ticker_id == ticker.id:
            asset = asset_in_portfolio
            break

    if not asset:
        asset = Asset(ticker_id=ticker.id,
                      portfolio_id=portfolio.id)
        db.session.add(asset)
        db.session.commit()

    return str(url_for('.asset_info',
                market_id=portfolio.market_id,
                only_content=request.args.get('only_content'),
                asset_id=asset.id))


@portfolio.route('/asset_settings')
@login_required
@demo_user_change
def asset_settings():
    asset = get_user_asset(request.args.get('asset_id'))
    return render_template('portfolio/asset_settings.html',
                           asset=asset)


@portfolio.route('/asset_settings_update', methods=['POST'])
@login_required
@demo_user_change
def asset_settings_update():
    """ Change asset """
    asset = get_user_asset(request.args.get('asset_id'))
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
@demo_user_change
def asset_info(market_id, asset_id):
    """ Asset page """
    if market_id != 'other':
        asset = get_user_asset(asset_id)
        if not asset:
            return ''

        portfolio_total_spent = 0
        for asset in asset.portfolio.assets:
            for transaction in asset.transactions:
                portfolio_total_spent += transaction.total_spent

        price_list = get_price_list(market_id)
        price = float_or_other(price_list.get(asset.ticker_id), 0)

        return render_template('portfolio/asset_info.html',
                               asset=asset,
                               price=price,
                               market_id=market_id,
                               portfolio_total_spent=portfolio_total_spent,
                               date=datetime.now().date())

    else:
        asset = get_user_other_asset(asset_id)
        if not asset:
            return ''

        portfolio_total_spent = 0
        for asset in asset.portfolio.other_assets:
            portfolio_total_spent += sum([body.total_spent for body in asset.bodys])

        return render_template('portfolio/other_asset_info.html',
                               asset=asset,
                               date=datetime.now().date(),
                               portfolio_total_spent=portfolio_total_spent)


@portfolio.route('/asset_info/<string:asset_id>')
@login_required
def asset_detail(asset_id):
    asset = get_user_asset(asset_id)
    if not asset:
        return ''

    price_list = get_price_list(asset.ticker.market_id)
    price = float_or_other(price_list.get(asset.ticker_id), 0)

    asset_quantity = 0
    asset_total_spent = 0
    for transaction in asset.transactions:
        asset_quantity += transaction.quantity
        asset_total_spent += transaction.total_spent

    cost_now = int(price * asset_quantity)
    profit = int(cost_now - asset_total_spent)
    profit_procent = ''
    if profit != 0 and asset_total_spent > 0:
        profit_procent = profit / asset_total_spent * 100
        profit_procent = '(' + str(int(abs(profit_procent))) + ')'
    profit_color = ''
    if profit > 0:
        profit_color = 'green'
        profit = '+$' + str(number_group(profit)) + profit_procent
    elif profit < 0:
        profit_color = 'red'
        profit = '-$' + str(number_group(abs(profit))) + profit_procent
    elif asset_quantity == 0:
        profit = ' - '
    else:
        profit = '$0'

    return {
        "price": number_group(smart_round(price)) if price else '-',
        "cost_now": '$' + str(number_group(cost_now)),
        "profit": profit,
        "profit_color": profit_color
    }


@portfolio.route('/transaction_action', methods=['POST'])
@login_required
@demo_user_change
def transactions_action():
    data = json.loads(request.data) if request.data else {}

    action = data.get('action')

    ids = data.get('ids')
    for id in ids:
        transaction = get_transaction(id)
        if not transaction:
            continue

        if action == 'delete':
            if transaction.order:
                # Мистика
                if transaction.alert:
                    db.session.delete(transaction.alert[0])
            db.session.delete(transaction)

        elif action == 'convert_to_transaction':
            transaction.order = 0
            transaction.date = datetime.now().date()


    db.session.commit()
    return ''


@portfolio.route('/<int:asset_id>/transaction', methods=['GET'])
@login_required
@demo_user_change
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
    asset = get_user_asset(asset_id)
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

    if transaction.type == 'Продажа':
        transaction.quantity *= -1
        transaction.total_spent *= -1

    if transaction.order:
        # Добавляем уведомление
        whitelist_ticker = get_whitelist_ticker(asset.ticker_id, True)
        price_list = get_price_list(asset.ticker.market_id)
        cost_now = float_or_other(price_list.get(asset.ticker_id), 0)

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

    # action = data.get('action')
    ids = data.get('ids')

    for id in ids:
        asset = get_user_other_asset(id)
        if not asset:
            continue

        if asset.bodys:
            for body in asset.bodys:
                db.session.delete(body)
        if asset.operations:
            for operation in asset.operations:
                db.session.delete(operation)
        db.session.delete(asset)

    db.session.commit()
    return ''


@portfolio.route('/<int:portfolio_id>/other_asset_settings', methods=['GET'])
@login_required
@demo_user_change
def other_asset_settings(portfolio_id):
    asset = get_user_other_asset(request.args.get('asset_id'))
    return render_template('portfolio/other_asset_settings.html',
                           asset=asset,
                           portfolio_id=portfolio_id)


@portfolio.route('/<int:portfolio_id>/other_asset_update', methods=['POST'])
@login_required
@demo_user_change
def other_asset_settings_update(portfolio_id):
    """ Add other asset to portfolio """
    asset = get_user_other_asset(request.args.get('asset_id'))
    if not asset:
        asset = otherAsset(portfolio_id=portfolio_id)
        db.session.add(asset)

    name = request.form.get('name')

    if asset.name != name:
        portfolio = get_user_portfolio(portfolio_id)
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


@portfolio.route('/other_asset_<int:asset_id>/operation', methods=['GET'])
@login_required
@demo_user_change
def other_asset_operation(asset_id):
    operation = get_operation(request.args.get('operation_id'))

    return render_template('portfolio/other_asset_operation.html',
                           asset_id=asset_id,
                           date=datetime.now().date(),
                           operation=operation)


@portfolio.route('/other_asset_<int:asset_id>/operation_update', methods=['POST'])
@login_required
@demo_user_change
def other_asset_operation_update(asset_id):
    """ Add or change operation of other asset """
    operation = get_operation(request.args.get('operation_id'))
    if not operation:
        operation = otherAssetOperation(asset_id=asset_id)
        db.session.add(operation)

    type = int(request.form['type'])
    total_spent = float(request.form['total_spent'])
    operation.total_spent = total_spent * type
    operation.type = 'Прибыль' if type == 1 else 'Убыток'
    operation.comment = request.form['comment']
    operation.date = request.form['date']

    db.session.commit()
    return ''


@portfolio.route('/other_asset_<int:asset_id>/body', methods=['GET'])
@login_required
@demo_user_change
def other_asset_body(asset_id):
    body = get_body(request.args.get('body_id'))

    return render_template('portfolio/other_asset_body.html',
                           asset_id=asset_id,
                           date=datetime.now().date(),
                           body=body)


@portfolio.route('/other_asset_<int:asset_id>/body_update', methods=['POST'])
@login_required
@demo_user_change
def other_asset_body_update(asset_id):
    """ Add or change body of other asset """
    body = get_body(request.args.get('body_id'))
    if not body:
        body = otherAssetBody(asset_id=asset_id)
        db.session.add(body)

    body.name = request.form['name']
    body.total_spent = float(request.form['total_spent'])
    body.cost_now = float(request.form['cost_now'])
    body.comment = request.form['comment']
    body.date = request.form['date']

    db.session.commit()
    return ''


@portfolio.route("/tickers/<string:market_id>")
@login_required
def ajax_tickers(market_id):
    per_page = 10
    search = request.args.get('search')
    result = {'results': []}

    query = Ticker.query.filter(Ticker.market_id == market_id).order_by(Ticker.id)
    if search:
        query = (query.where(Ticker.name.contains(search),
                             Ticker.symbol.contains(search)))

    tickers = query.paginate(page=int_or_other(request.args.get('page')),
                             per_page=per_page,
                             error_out=False)

    for ticker in tickers:
        item = {
            'id': ticker.id,
            'name': ticker.name,
            'symbol': ticker.symbol.upper()
        }
        if ticker.market_cap_rank:
            item['cap_rank'] = '#' + str(ticker.market_cap_rank)
        if ticker.image:
            item['image'] = ticker.image 
        result['results'].append(item)
    more = len(result['results']) >= per_page
    result['pagination'] = {'more': more}

    return json.dumps(result)
