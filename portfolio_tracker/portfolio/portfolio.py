import json
import pickle
from datetime import datetime
from flask import flash, render_template, redirect, url_for, request, session, abort, Blueprint
from flask_login import login_required, current_user
from transliterate import slugify

from portfolio_tracker.app import db, redis
from portfolio_tracker.general_functions import dict_get_or_other, float_or_other, price_list_def
from portfolio_tracker.jinja_filters import number_group, smart_round
from portfolio_tracker.models import Portfolio, Asset, Ticker, otherAsset, \
        otherAssetOperation, otherAssetBody, Wallet, Transaction, Alert, \
        User, Trackedticker, Feedback
from portfolio_tracker.wallet.wallet import get_user_wallet
# from portfolio_tracker.defs import number_group, smart_round
from portfolio_tracker.wraps import demo_user_change


portfolio = Blueprint('portfolio', __name__, template_folder='templates', static_folder='static')


def int_or_other(number, default=0):
    return int(number) if number else default


def get_user_portfolio(id):
    return db.session.execute(
        db.select(Portfolio).filter_by(id=id,
                                       user_id=current_user.id)).scalar()


def get_ticker(id):
    if not id:
        return None
    return db.session.execute(db.select(Ticker).filter_by(id=id)).scalar()

def get_alert(asset_id, price):
    return db.session.execute(
        db.select(Alert).filter_by(asset_id=asset_id,
                                   price=price)).scalar()


def get_user_asset(market_id, asset_id):
    if market_id == 'other':
        select = db.select(otherAsset).filter_by(id=asset_id)
    else:
        select = db.select(Asset).filter_by(id=asset_id)
    return db.session.execute(select).scalar()


def get_transaction(id):
    if not id:
        return None
    transaction = db.session.execute(
        db.select(Transaction).filter_by(id=id)).scalar()
    if transaction.asset.portfolio.user_id == current_user.id:
        return transaction
    else:
        return None


@portfolio.route('/', methods=['GET'])
@login_required
def portfolios():
    """ Portfolios page """
    session['last_url'] = request.url
    price_list = price_list_def()
    total_spent = cost_now = 0
    total_spent_list = {}
    cost_now_list = {}
    orders_in_portfolio = []
    for portfolio in current_user.portfolios:
        if portfolio.assets:
            for asset in portfolio.assets:
                total_spent += asset.total_spent
                asset_price = price_list.get(asset.ticker.id)
                if asset_price:
                    cost_now += asset.quantity * asset_price
                    for transaction in asset.transactions:
                        if not transaction.order:
                            total_spent_list[portfolio.id] = \
                                (float(total_spent_list.
                                 setdefault(portfolio.id, 0))
                                 + float(transaction.total_spent))

                            cost_now_list[portfolio.id] = \
                                (float(cost_now_list.
                                 setdefault(portfolio.id, 0))
                                 + float(transaction.quantity)
                                 * float(asset_price))
                        else:
                            orders_in_portfolio.append(portfolio.id)

        else:
            for asset in portfolio.other_assets:
                total_spent += \
                    sum([body.total_spent for body in asset.bodys])
                cost_now += \
                    (sum([body.cost_now for body in asset.bodys])
                     + sum([operation.total_spent
                            for operation in asset.operations]))

                total_spent_list[portfolio.id] = \
                    (float(total_spent_list.
                     setdefault(portfolio.id, 0))
                     + float(sum([body.total_spent
                                  for body in asset.bodys])))
                cost_now_list[portfolio.id] = \
                    (float(cost_now_list.
                     setdefault(portfolio.id, 0))
                     + float(sum([body.cost_now for body in asset.bodys])
                     + sum([operation.total_spent
                            for operation in asset.operations])))

    return render_template('portfolio/portfolios.html',
                           # portfolios=user_portfolios,
                           total_spent=total_spent,
                           cost_now=cost_now,
                           total_spent_list=total_spent_list,
                           cost_now_list=cost_now_list,
                           orders_in_portfolio=orders_in_portfolio)


@portfolio.route('/portfolio_settings', methods=['GET'])
@login_required
def portfolio_settings():
    portfolio = get_user_portfolio(request.args.get('portfolio_id'))
    load_only_content = request.args.get('load_only_content')
    return render_template('portfolio/portfolio_settings.html',
                           portfolio=portfolio,
                           load_only_content=load_only_content)


@portfolio.route('/new_portfolio', methods=['POST'])
@portfolio.route('/portfolio_<int:portfolio_id>/update', methods=['POST'])
@login_required
@demo_user_change
def portfolio_update(portfolio_id=None):
    """ Add or change portfolio """
    name = request.form['name']
    comment = request.form['comment']
    market_id=request.form['market_id']

    portfolio = get_user_portfolio(portfolio_id)
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

    portfolio.name = name
    portfolio.comment = comment
    db.session.commit()

    return redirect(url_for('.portfolios'))



@portfolio.route('/action', methods=['POST'])
@login_required
@demo_user_change
def portfolio_action():
    """ Action portfolio """
    data = json.loads(request.data) if request.data else {}

    action = data.get('action')
    ids = data.get('ids')

    # for id in ids:
    for portfolio in current_user.portfolios:
        if str(portfolio.id) not in ids:
            continue

        nw_a_redis = redis.get('not_worked_alerts')
        not_worked_alerts = pickle.loads(nw_a_redis) if nw_a_redis else {}
        w_a_redis = redis.get('worked_alerts')
        worked_alerts = pickle.loads(w_a_redis) if w_a_redis else {}
        for asset in portfolio.assets:
            if asset.transactions:
                flash('В портфеле ' + portfolio.name + ' есть транзакции')
            for alert in asset.alerts:
                # отставляем уведомления
                alert.asset_id = None
                alert.comment = ('Портфель ' + str(asset.portfolio.name)
                                             + ' удален')
                # redis
                not_worked_alerts.pop(alert.id, None)
                if worked_alerts != {}:
                    for i in worked_alerts[current_user.id]:
                        if i['id'] == alert.id:
                            worked_alerts[current_user.id].remove(i)
                            break
        redis.set('worked_alerts', pickle.dumps(worked_alerts))
        redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))

        db.session.delete(portfolio)
    db.session.commit()
    return redirect(url_for('.portfolios', user_id=current_user.id))


@portfolio.route('/portfolio_<int:portfolio_id>', methods=['GET'])
@login_required
def portfolio_info(portfolio_id):
    """ Portfolio page """
    load_only_content = request.args.get('load_only_content')
    price_list = price_list_def()

    portfolio = get_user_portfolio(portfolio_id)
    if not portfolio:
        return redirect(url_for('.portfolios'))

    # crypto or stocks
    if portfolio.market_id != 'other':
        tickers_in_base = db.session.execute(
                db.select(Ticker).
                filter_by(market=portfolio.market)).scalars()
        cost_now = 0
        for asset in portfolio.assets:
            asset_price = price_list.get(asset.ticker.id)
            if asset_price:
                cost_now += (asset.quantity * asset_price)
        return render_template('portfolio/portfolio_info.html',
                               portfolio=portfolio,
                               price_list=price_list,
                               cost_now=cost_now,
                               load_only_content=load_only_content,
                               tickers=tickers_in_base)
    # other assets
    else:
        cost_now = 0
        portfolio_total_spent = 0
        for asset in portfolio.other_assets:
            portfolio_total_spent += sum([body.total_spent
                                          for body in asset.bodys])
            cost_now += sum([body.cost_now
                                       for body in asset.bodys])
            cost_now += sum([operation.total_spent
                                       for operation in asset.operations])
        return render_template('portfolio/other_portfolio_info.html',
                               portfolio=portfolio,
                               price_list=price_list,
                               portfolio_cost_now=cost_now,
                               portfolio_total_spent=portfolio_total_spent,
                               tickers={})


@portfolio.route('/<string:market_id>/asset_<int:asset_id>')
@login_required
def asset_info(market_id, asset_id):
    """ Asset page """
    load_only_content = request.args.get('load_only_content')
    asset = get_user_asset(market_id, asset_id)
    if market_id != 'other':
        price_list = price_list_def()
        price = price_list.get(asset.ticker_id) if asset else 0

        return render_template('portfolio/asset_info.html',
                               asset=asset,
                               price=price,
                               market_id=market_id,
                               date=datetime.now().date(),
                               load_only_content=load_only_content
                               )

    elif market_id == 'other':
        portfolio_total_spent = 0
        # portfolio = get_user_portfolio()
        # for portfolio in current_user.portfolios:
        #     if portfolio.url == portfolio_url:
        #         for asset in portfolio.other_assets:
        #             portfolio_total_spent += sum([body.total_spent
        #                                           for body in asset.bodys])
                    # if asset.url == asset_url:
                    #     asset_in_base = asset
        return render_template('portfolio/other_asset_info.html',
                               asset=asset,
                               date=datetime.now().date(),
                               portfolio_total_spent=portfolio_total_spent)
    if not asset:
        abort(404)


@portfolio.route('<string:market_id>/asset_settings')
@login_required
def asset_settings(market_id):
    asset_id = request.args.get('asset_id')
    asset = get_user_asset(market_id, asset_id)
    return render_template('portfolio/asset_settings.html',
                           asset=asset)


@portfolio.route('/asset_info/<string:asset_id>')
def asset_detail(asset_id):
    asset = db.session.execute(
            db.select(Asset).filter_by(id=asset_id)).scalar()
    price_list = price_list_def()
    price = price_list.get(asset.ticker_id)
    price = price if price else '-'
    cost_now = price * asset.quantity
    profit = int(round(cost_now - asset.total_spent))
    profit_color = ''
    if profit > 0:
        profit_color = 'green'
        profit = '+$' + str(number_group(int(round(profit))))
    elif profit < 0:
        profit_color = 'red'
        profit = '-$' + str(number_group(abs(int(round(profit)))))
    elif asset.quantity == 0:
        profit = ' - '
    else:
        profit = '$0'

    return {
        "price": number_group(smart_round(price)),
        "cost_now": '$' + str(number_group(
            int(round(cost_now)))) if asset.quantity > 0 else '-',
        "profit": profit,
        "profit_color": profit_color,
        "profit_procent": ('(' + str(
            int(round(abs((cost_now - asset.total_spent) /
                          asset.total_spent * 100))))
                          + '%)') if asset.total_spent > 0 else ''
    }


@portfolio.route('/<string:market_id>/asset_update', methods=['POST'])
@login_required
@demo_user_change
def asset_update(market_id):
    """ Change asset """
    asset = get_user_asset(market_id, request.args.get('id'))
    if asset:
        comment = request.form.get('comment')
        percent = request.form.get('percent')
        if comment != None:
            asset.comment = comment
        if percent != None:
            asset.percent = percent
        db.session.commit()
    return 'OK'


@portfolio.route('/<string:market_id>/asset_delete', methods=['POST'])
@login_required
@demo_user_change
def asset_action(market_id):
    """ Asset action """
    data = json.loads(request.data) if request.data else {}

    action = data.get('action')
    ids = data.get('ids')

    for id in ids:
        asset = get_user_asset(market_id, id)
        if asset:
            for transaction in asset.transactions:
                # if transaction.order and transaction.type != 'Продажа':
                    # wallet_in_base = db.session.execute(
                    #         db.select(Wallet).
                    #         filter_by(id=transaction.wallet_id)).scalar()
                    # wallet_in_base.money_in_order -= float(transaction.total_spent)
                db.session.delete(transaction)

            alerts_redis = redis.get('not_worked_alerts')
            not_worked_alerts = pickle.loads(alerts_redis) if alerts_redis else {}
            alerts_redis = redis.get('worked_alerts')
            worked_alerts = pickle.loads(alerts_redis) if alerts_redis else {}
            for alert in asset.alerts:
                # оставляем уведомления
                alert.asset_id = None
                alert.comment = ('Актив удален из портфеля '
                                 + str(asset.portfolio.name))
                # redis
                not_worked_alerts.pop(alert.id, None)
                if worked_alerts != {}:
                    for i in worked_alerts[current_user.id]:
                        if i['id'] == alert.id:
                            worked_alerts[current_user.id].remove(i)
                            break

            db.session.delete(asset)
            db.session.commit()

    return redirect(url_for('.portfolio_info', portfolio_id=asset.portfolio_id))


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


@portfolio.route('/<int:portfolio_id>/add', methods=['GET'])
@login_required
@demo_user_change
def asset_add(portfolio_id):
    """ Add asset to portfolio """
    load_only_content = request.args.get('load_only_content')
    ticker_id = request.args.get('ticker_id')

    ticker = get_ticker(ticker_id)
    portfolio = get_user_portfolio(portfolio_id)
    if not ticker or not portfolio:
        return ''

    asset = None
    for asset_in_portfolio in portfolio.assets:
        if asset_in_portfolio.ticker_id == ticker.id:
            asset = asset_in_portfolio
            break

    if not asset:
        asset = Asset(ticker_id=ticker_id,
                      portfolio_id=portfolio.id)
        db.session.add(asset)
        db.session.commit()

    return redirect(url_for('.asset_info',
                market_id=portfolio.market_id,
                load_only_content=load_only_content,
                asset_id=asset.id))


@portfolio.route('/<string:market_id>/<int:portfolio_id>/other_asset_add', methods=['POST'])
@login_required
@demo_user_change
def other_asset_add(market_id, portfolio_id):
    """ Add other asset to portfolio """
    asset = get_user_asset(market_id, request.form.get('id'))
    portfolio = get_user_portfolio(portfolio_id)

    name = request.form.get('name')
    n = 2
    while name in [i.name for i in portfolio.assets]:
        name = request.form.get('name') + str(n)
        n += 1

    if not asset:
        asset = otherAsset(portfolio_id=portfolio.id)
        db.session.add(asset)

    asset.name = name
    asset.percent = dict_get_or_other(request.form, 'percent', 0)
    asset.comment = request.form.get('comment')
    db.session.commit()

    return redirect(url_for('.asset_info',
                            market_id=market_id,
                            asset_id=asset.id))


@portfolio.route('/<string:market_id>/asset_action', methods=['POST'])
@login_required
@demo_user_change
def other_asset_action(market_id):
    """ Delete other asset """
    data = json.loads(request.data) if request.data else {}

    action = data.get('action')
    ids = data.get('ids')

    for id in ids:
        asset = get_user_asset(market_id, id)
    # if request.form.get('type') == 'asset_body':
    #     asset_body = db.session.execute(
    #             db.select(otherAssetBody).filter_by(id=id)).scalar()
    #     db.session.delete(asset_body)
    # elif request.form.get('type') == 'asset_operation':
    #     asset_operation = db.session.execute(
    #         db.select(otherAssetOperation).filter_by(id=id)).scalar()
    #     db.session.delete(asset_operation)
        if asset.bodys:
            for body in asset.bodys:
                db.session.delete(body)
        if asset.operations:
            for operation in asset.operations:
                db.session.delete(operation)
        db.session.delete(asset)

    db.session.commit()
    return ''


@portfolio.route('/<string:market_id>/<int:asset_id>/update', methods=['POST'])
# @portfolio.route('/<int:portfolio_id>/transaction_add', methods=['POST'])
@login_required
@demo_user_change
def transaction_update(market_id, asset_id):
    """ Add or change transaction """
    load_only_content = request.args.get('load_only_content')
    asset = get_user_asset(market_id, asset_id)
    wallet = get_user_wallet(request.form.get('wallet_id'))

    transaction_id = request.args.get('id')

    if transaction_id:
        transaction = get_transaction(transaction_id)
        if not transaction:
            return redirect(url_for('.asset_info',
                                    market_id=market_id,
                                    asset_id=asset_id))
    else:
        transaction = Transaction(asset_id=asset_id)
        db.session.add(transaction)


    transaction.price = float_or_other(request.form.get('price'))
    transaction.total_spent = float_or_other(request.form.get('total_spent'))
    transaction.type = request.form['type']
    transaction.comment = request.form['comment']
    transaction.date = request.form['date']
    transaction.order = bool(request.form.get('order'))
    transaction.wallet_id = request.form.get('wallet_id')
    transaction.quantity = transaction.total_spent / transaction.price

    if transaction.type == 'Продажа':
        transaction.quantity *= -1
        transaction.total_spent *= -1

    # if transaction.order:
    #     price_list = price_list_def()
        # if transaction.type != 'Продажа':
        #     wallet.money_in_order += transaction.total_spent

        # Добавляем уведомление
        # alert = Alert(
        #     price=transaction.price,
        #     date=transaction.date,
        #     comment='Ордер',
        #     asset_id=asset_id,
        #     type='down' if (
        #         price_list[asset.ticker_id]) > transaction.price else 'up'
        # )
        # tracked_ticker_in_base = db.session.execute(
        #     db.select(Trackedticker).
        #     filter_by(ticker_id=asset_in_base.ticker_id,
        #               user_id=current_user.id)).scalar()
        # if not tracked_ticker_in_base:
        #     tracked_ticker = Trackedticker(
        #             ticker_id=asset_in_base.ticker_id,
        #             user_id=current_user.id)
        #     db.session.add(tracked_ticker)
        #     db.session.commit()
        #     alert.trackedticker_id = tracked_ticker.id
        # else:
        #     alert.trackedticker_id = tracked_ticker_in_base.id

        # db.session.add(alert)
        # db.session.commit()

        # return 'OK'




            # записываем в список уведомлений
            # alerts_redis = redis.get('not_worked_alerts')
            # not_worked_alerts = pickle.loads(
            #         alerts_redis) if alerts_redis else {}
            # not_worked_alerts[alert.id] = {}
            # not_worked_alerts[alert.id]['type'] = alert.type
            # not_worked_alerts[alert.id]['price'] = alert.price
            # not_worked_alerts[alert.id]['ticker_id'] = asset_in_base.ticker_id
            # redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))

        # else:
        #     asset_in_base.quantity += transaction.quantity
        #     asset_in_base.total_spent += float(transaction.total_spent)
        # db.session.add(transaction)

    db.session.commit()
    return redirect(url_for('.asset_info',
                            market_id=market_id,
                            load_only_content=load_only_content,
                            asset_id=asset_id))


@portfolio.route('/<string:market_id>/<int:asset_id>/transaction_action',
           methods=['POST'])
@login_required
@demo_user_change
def transactions_action(market_id, asset_id):
    data = json.loads(request.data) if request.data else {}

    action = data.get('action')

    ids = data.get('ids')
    for id in ids:
        transaction = get_transaction(id)
        if not transaction:
            continue

        if action == 'delete':
            db.session.delete(transaction)
        elif action == 'convert_to_transaction':
            transaction.order = 0
            transaction.date = datetime.now().date()


        if transaction.order:
            pass
            # if transaction.type != 'Продажа':
            #     wallet_in_base = db.session.execute(
            #             db.select(Wallet).
            #             filter_by(id=transaction.wallet_id)).scalar()
            #     wallet_in_base.money_in_order -= float(transaction.total_spent)

            # удаляем уведомление
            # alert = get_alert(asset_id, transaction.price)
            # db.session.delete(alert)
    # else:
    #     asset.quantity -= transaction.quantity
    #     asset.total_spent -= transaction.total_spent
    db.session.commit()
    return redirect(url_for('.asset_info',
                            market_id=market_id,
                            asset_id=asset_id))


@portfolio.route('<string:market_id>/<int:asset_id>/transaction', methods=['GET'])
@login_required
@demo_user_change
def transaction(market_id, asset_id):
    load_only_content = request.args.get('load_only_content')
    transaction = get_transaction(request.args.get('transaction_id'))
    price = 0

    if not transaction:
        price_list = price_list_def()
        price = price_list.get(request.args.get('ticker'))

    return render_template('portfolio/transaction.html',
                           transaction=transaction,
                           date=datetime.now().date(),
                           market_id=market_id,
                           asset_id=asset_id,
                           load_only_content=load_only_content,
                           price=price)


@portfolio.route('<string:market_id>/<int:asset_id>/alerts', methods=['GET'])
@login_required
@demo_user_change
def asset_alerts(market_id, asset_id):
    asset = get_user_asset(market_id, asset_id)
    price_list = price_list_def()
    price = price_list.get(asset.ticker_id)

    return render_template('portfolio/alerts.html',
                           asset=asset,
                           price=price
                           )
