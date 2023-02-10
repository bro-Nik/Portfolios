from flask import render_template, redirect, url_for, request, flash, session, jsonify, abort
from flask_login import login_user, login_required, logout_user, current_user
from transliterate import slugify
import os
import requests
from celery import Celery
from werkzeug.security import check_password_hash, generate_password_hash

from portfolio_tracker.app import login_manager
from portfolio_tracker.models import *
from portfolio_tracker.defs import *


@app.route('/settings')
@login_required
def settings():
    ''' Страница настроек '''
    return render_template('settings.html')


@app.route('/settings/update', methods=['POST'])
def settings_update():
    ''' Изменение настроек '''
    return redirect(url_for('settings'))


@app.route('/', methods=['GET'])
@login_required
def portfolios():
    ''' Страница портфелей '''
    session['last_url'] = request.url
    price_list = price_list_def()
    portfolios = tuple(db.session.execute(db.select(Portfolio).filter_by(user_id=current_user.id)).scalars())
    total_spent = cost_now = 0
    total_spent_list = {}
    cost_now_list = {}
    orders_in_portfolio = []
    if portfolios != ():
        for portfolio in portfolios:
            if portfolio.assets:
                for asset in portfolio.assets:
                    total_spent += asset.total_spent
                    cost_now += (asset.quantity * price_list[asset.ticker.id])
                    for transaction in asset.transactions:
                        if not transaction.order:
                            total_spent_list[portfolio.id] = float(total_spent_list.setdefault(portfolio.id, 0)) + float(transaction.total_spent)
                            cost_now_list[portfolio.id] = float(cost_now_list.setdefault(portfolio.id, 0)) + float(transaction.quantity) * float(price_list[asset.ticker.id])
                        else:
                            orders_in_portfolio.append(portfolio.id)
            else:
                for asset in portfolio.other_assets:
                    total_spent += sum([body.total_spent for body in asset.bodys])
                    cost_now += sum([body.cost_now for body in asset.bodys]) + sum([operation.total_spent for operation in asset.operations])

                    total_spent_list[portfolio.id] = float(total_spent_list.setdefault(portfolio.id, 0)) + float(sum([body.total_spent for body in asset.bodys]))
                    cost_now_list[portfolio.id] = float(cost_now_list.setdefault(portfolio.id, 0)) + float(sum([body.cost_now for body in asset.bodys]) + sum([operation.total_spent for operation in asset.operations]))

    return render_template('portfolios.html', portfolios=portfolios, total_spent=total_spent, cost_now=cost_now, total_spent_list=total_spent_list, cost_now_list=cost_now_list, orders_in_portfolio=orders_in_portfolio)


@app.errorhandler(404)
@login_required
def page_not_found(e):
    return render_template('404.html')

@app.route('/portfolio_add', methods=['POST'])
@login_required
def portfolio_add():
    ''' Добавление и изменение портфеля '''
    def create_url():
        return slugify(str(portfolio.name)) if slugify(str(portfolio.name)) else portfolio.name

    portfolio = Portfolio(
        name=request.form['name'],
        comment=request.form['comment'],
        market_id=request.form['market_id'],
        user_id=current_user.id
    )

    if request.form.get('id'):
        portfolio_in_base = db.session.execute(db.select(Portfolio).filter_by(id=request.form.get('id'), user_id=current_user.id)).scalar()
        portfolio_in_base.name = portfolio.name
        portfolio_in_base.url = create_url()
        portfolio_in_base.comment = portfolio.comment
        db.session.commit()

    else:
        portfolio_in_base = db.session.execute(db.select(Portfolio).filter_by(name=portfolio.name, market_id=portfolio.market_id, user_id=current_user.id)).scalar()
        if portfolio_in_base:
            n = 2
            while portfolio.name in [i.name for i in current_user.portfolios if i.market_id == portfolio.market_id]:
                portfolio.name = str(portfolio_in_base.name) + str(n)
                n += 1

        portfolio.url = create_url()
        db.session.add(portfolio)
        db.session.commit()
        return redirect(url_for('portfolio_info', market_id=portfolio.market_id, portfolio_url=portfolio.url))

    return redirect(url_for('portfolios'))

@app.route('/portfolio_delete', methods=['POST'])
@login_required
def portfolio_delete():
    ''' Удаление портфеля '''
    portfolio_in_base = db.session.execute(db.select(Portfolio).filter_by(id=request.form.get('id'), user_id=current_user.id)).scalar()
    if portfolio_in_base:
        for asset in portfolio_in_base.assets:
            for alert in asset.alerts:
                # удаляем уведомления
                #all_alerts_list['worked'].pop(alert.id, None)
                #all_alerts_list['not_worked'].pop(alert.id, None)
                #db.session.delete(alert)
                # отставляем уведомления
                alert.asset_id = None
                alert.comment = 'Портфель ' + str(asset.portfolio.name) + ' удален'

        db.session.delete(portfolio_in_base)
        db.session.commit()
    return redirect(url_for('portfolios', user_id=current_user.id))

@app.route('/<string:market_id>/<string:portfolio_url>', methods=['GET'])
@login_required
def portfolio_info(market_id, portfolio_url):
    ''' Страница портфеля '''
    session['last_url'] = request.url
    price_list = price_list_def()
    portfolio_in_base = db.session.execute(db.select(Portfolio).filter_by(url=portfolio_url, market_id=market_id, user_id=current_user.id)).scalar()
    if portfolio_in_base:
        if portfolio_in_base.market_id != 'other':
            tickers_in_base = db.session.execute(db.select(Ticker).filter_by(market=portfolio_in_base.market)).scalars()
            portfolio_cost_now = 0
            for asset in portfolio_in_base.assets:
                portfolio_cost_now += (asset.quantity * price_list[asset.ticker.id])
            return render_template('portfolio_info.html', portfolio=portfolio_in_base, price_list=price_list, portfolio_cost_now=portfolio_cost_now, tickers=tickers_in_base)
        else:
            portfolio_cost_now = 0
            portfolio_total_spent = 0
            for asset in portfolio_in_base.other_assets:
                portfolio_total_spent += sum([body.total_spent for body in asset.bodys])
                portfolio_cost_now += sum([body.cost_now for body in asset.bodys])
                portfolio_cost_now += sum([operation.total_spent for operation in asset.operations])
            return render_template('other_portfolio_info.html', portfolio=portfolio_in_base, price_list=price_list, portfolio_cost_now=portfolio_cost_now, portfolio_total_spent=portfolio_total_spent, tickers={})
    else:
        return redirect(url_for('portfolios'))


@app.route('/<string:market_id>/<string:portfolio_id>/add/<string:ticker_id>', methods=['GET'])
@login_required
def asset_add(market_id, portfolio_id, ticker_id):
    ''' Добавление актива в портфель '''
    new_asset = Asset(
        percent=0,
        total_spent=0,
        quantity=0
    )
    ticker_in_base = db.session.execute(db.select(Ticker).filter_by(id=ticker_id)).scalar()
    portfolio_in_base = db.session.execute(db.select(Portfolio).filter_by(id=portfolio_id, user_id=current_user.id)).scalar()
    if ticker_in_base and portfolio_in_base:
        #portfolio_id = portfolio_in_base.id,
        asset_in_portfolio = False
        for asset in portfolio_in_base.assets:
            if asset.ticker_id == ticker_in_base.id:
                asset_in_portfolio = True
                break

        if not asset_in_portfolio:
            new_asset.ticker_id = ticker_id
            new_asset.portfolio_id = portfolio_in_base.id
            db.session.add(new_asset)
            db.session.commit()

    return redirect(url_for('asset_info', market_id=market_id, portfolio_url=portfolio_in_base.url, asset_url=ticker_id))

@app.route('/<string:market_id>/<string:portfolio_url>/other_asset_add', methods=['POST'])
@login_required
def other_asset_add(market_id, portfolio_url):
    ''' Добавление актива в портфель '''
    new_asset = otherAsset(
        name=request.form.get('name'),
        percent=request.form.get('percent') if request.form.get('percent') else 0,
        comment=request.form.get('comment'),
        total_spent=0
    )
    # Если обновление
    if request.form.get('id'):
        asset_in_base = db.session.execute(db.select(otherAsset).filter_by(id=request.form.get('id'))).scalar()
        asset_in_base.name = new_asset.name
        asset_in_base.percent = new_asset.percent
        asset_in_base.comment = new_asset.comment
        asset_url = asset_in_base.url
        db.session.add(new_asset)
        db.session.commit()

    # Если добавление
    else:
        portfolio_in_base = db.session.execute(db.select(Portfolio).filter_by(url=portfolio_url, user_id=current_user.id)).scalar()
        if portfolio_in_base:
            n = 2
            while new_asset.name in [i.name for i in portfolio_in_base.assets]:
                new_asset.name += str(n)
                n += 1
            new_asset.url = slugify(str(new_asset.name)) if slugify(str(new_asset.name)) else new_asset.name
            new_asset.portfolio_id = portfolio_in_base.id
            asset_url = new_asset.url
            db.session.add(new_asset)
            db.session.commit()

    return redirect(url_for('asset_info', market_id=market_id, portfolio_url=portfolio_url, asset_url=asset_url))


@app.route('/<string:market_id>/<string:portfolio_url>/asset_update', methods=['POST'])
@login_required
def asset_update(market_id, portfolio_url):
    ''' Изменение актива '''
    asset_in_base = db.session.execute(db.select(Asset).filter_by(id=request.form.get('id'))).scalar()
    if asset_in_base:
        if request.form.get('percent'):
            asset_in_base.percent = request.form.get('percent') if request.form.get('percent') else 0
        if request.form.get('comment'):
            asset_in_base.comment = request.form.get('comment')
        db.session.commit()
    return redirect(session['last_url'])

@app.route('/<string:market_id>/<string:portfolio_url>/asset_delete', methods=['POST'])
@login_required
def asset_delete(market_id, portfolio_url):
    ''' Удаление актива '''
    asset_in_base = db.session.execute(db.select(Asset).filter_by(id=request.form.get('id'))).scalar()
    if asset_in_base:
        for transaction in asset_in_base.transactions:
            if transaction.order:
                wallet_in_base = db.session.execute(db.select(Wallet).filter_by(id=transaction.wallet_id)).scalar()
                wallet_in_base.money_in_order -= float(transaction.total_spent)
            db.session.delete(transaction)

        for alert in asset_in_base.alerts:
            # удаляем уведомления
            #all_alerts_list['worked'].pop(alert.id, None)
            #all_alerts_list['not_worked'].pop(alert.id, None)
            #db.session.delete(alert)
            # оставляем уведомления
            alert.asset_id = None
            alert.comment = 'Актив удален из портфеля ' + str(asset_in_base.portfolio.name)

        db.session.delete(asset_in_base)
        db.session.commit()

    return redirect(url_for('portfolio_info', market_id=market_id, portfolio_url=portfolio_url))


@app.route('/<string:market_id>/<string:portfolio_url>/<string:asset_url>')
@login_required
def asset_info(market_id, portfolio_url, asset_url):
    ''' Страница актива в портфеле '''
    session['last_url'] = request.url
    if market_id != 'other':
        wallets = current_user.wallets
        for portfolio in current_user.portfolios:
            if portfolio.url == portfolio_url:
                for asset in portfolio.assets:
                    if asset.ticker_id == asset_url:
                        asset_in_base = asset
                        break

        price_list = price_list_def()
        price = float(price_list[asset_in_base.ticker_id])

        return render_template('asset_info.html', asset=asset_in_base, price=price, date=date, wallets=tuple(wallets))

    if market_id == 'other':
        portfolio_total_spent = 0
        for portfolio in current_user.portfolios:
            if portfolio.url == portfolio_url:
                for asset in portfolio.other_assets:
                    portfolio_total_spent += sum([body.total_spent for body in asset.bodys])
                    if asset.url == asset_url:
                        asset_in_base = asset
                        break

        return render_template('other_asset_info.html', asset=asset_in_base, date=date, portfolio_total_spent=portfolio_total_spent)

@app.route("/json/asset_info/<string:asset_id>")
def asset_detail(asset_id):
    asset_in_base = db.session.execute(db.select(Asset).filter_by(id=asset_id)).scalar()
    price_list = price_list_def()
    price = price_list[asset_in_base.ticker_id]
    cost_now = price * asset_in_base.quantity
    profit = int(round(cost_now - asset_in_base.total_spent))
    profit_color = ''
    if profit > 0:
        profit_color = 'green'
        profit = '+$' + str(number_group(int(round(profit))))
    elif profit < 0:
        profit_color = 'red'
        profit = '-$' + str(number_group(abs(int(round(profit)))))
    elif asset_in_base.quantity == 0:
        profit = ' - '
    else:
        profit = '$0'

    when_updated = when_updated_def(price_list[str('update-' + asset_in_base.portfolio.market_id)])

    alerts = []
    for alert in asset_in_base.alerts:
        alerts.append({'id': alert.id, 'price': number_group(alert.price), 'worked': alert.worked})

    return {
        "price": number_group(smart_round(price)),
        "cost_now": '$' + str(number_group(int(round(cost_now)))) if asset_in_base.quantity > 0 else '-',
        "profit": profit,
        "profit_color": profit_color,
        "profit_procent": '(' + str(int(round(abs((cost_now - asset_in_base.total_spent) / asset_in_base.total_spent * 100)))) + '%)' if asset_in_base.total_spent > 0 else '',
        "when_updated": when_updated,
        "alerts": alerts
    }

@app.route('/<string:market_id>/<string:portfolio_url>/transaction_add', methods=['POST'])
@login_required
def transaction_add(market_id, portfolio_url):
    ''' Добавление или изменение транзакции '''
    asset_in_base = db.session.execute(db.select(Asset).filter_by(id=request.form['asset_id'])).scalar()
    wallet_in_base = db.session.execute(db.select(Wallet).filter_by(id=request.form['wallet_id'])).scalar()
    # добавление новой транзакции
    if request.form['add_or_change'] == 'add':
        transaction = Transaction(
            asset_id=request.form['asset_id'],
            price=request.form['price'].replace(',', '.'),
            total_spent=request.form['total_spent'].replace(',', '.'),
            type=request.form['type'],
            comment=request.form['comment'],
            date=request.form['date'],
            order=bool(request.form['order'])
        )
        transaction.wallet_id = wallet_in_base.id
        if transaction.type == 'Покупка':
            transaction.quantity = float(transaction.total_spent) / float(transaction.price)
        if transaction.type == 'Продажа':
            transaction.quantity = float(transaction.total_spent) / float(transaction.price) * -1
            transaction.total_spent = float(transaction.total_spent) * -1

        if transaction.order:
            price_list = price_list_def()
            wallet_in_base.money_in_order += float(transaction.total_spent)
            # Добавляем уведомление
            alert = Alert(
                price=transaction.price,
                date=transaction.date,
                comment='Ордер',
                asset_id=transaction.asset_id,
                type='down' if float(price_list[asset_in_base.ticker_id]) > float(transaction.price) else 'up'
            )
            tracked_ticker_in_base = db.session.execute(db.select(Trackedticker).filter_by(ticker_id=asset_in_base.ticker_id, user_id=current_user.id)).scalar()
            if not tracked_ticker_in_base:
                tracked_ticker = Trackedticker(ticker_id=asset_in_base.ticker_id, user_id=current_user.id)
                db.session.add(tracked_ticker)
                db.session.commit()
                alert.trackedticker_id = tracked_ticker.id
            else:
                alert.trackedticker_id = tracked_ticker_in_base.id

            db.session.add(alert)
            db.session.commit()
            # записываем в список уведомлений
            not_worked_alerts = pickle.loads(redis.get('not_worked_alerts')) if redis.get('not_worked_alerts') else {}
            not_worked_alerts[alert.id] = {}
            not_worked_alerts[alert.id]['type'] = alert.type
            not_worked_alerts[alert.id]['price'] = alert.price
            not_worked_alerts[alert.id]['ticker_id'] = asset_in_base.ticker_id
            redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))

        else:
            asset_in_base.quantity += transaction.quantity
            asset_in_base.total_spent += float(transaction.total_spent)
        db.session.add(transaction)
    # изменение сужествующей транзакции
    if request.form['add_or_change'] == 'change':
        transaction = db.session.execute(db.select(Transaction).filter_by(id=request.form['id'])).scalar()
        transaction.date = request.form['date']
        transaction.comment = request.form['comment']
        new_price = float(request.form['price'].replace(',', '.'))
        new_total_spent = float(request.form['total_spent'].replace(',', '.'))

        if transaction.price != new_price or transaction.total_spent != new_total_spent:
            if transaction.type == 'Покупка':
                new_quantity = new_total_spent / new_price
            if transaction.type == 'Продажа':
                new_quantity = new_total_spent / new_price * -1
                new_total_spent = new_total_spent * -1

            if transaction.order:
                # изменяем уведомление
                alert_in_base = db.session.execute(db.select(Alert).filter_by(asset_id=transaction.asset_id, price=transaction.price)).scalar()
                alert_in_base.price = new_price
                # redis
                not_worked_alerts = pickle.loads(redis.get('not_worked_alerts')) if redis.get('not_worked_alerts') else {}
                if not_worked_alerts.get(alert_in_base.id):
                    not_worked_alerts[alert_in_base.id]['price'] = new_price
                redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))
            else:
                transaction.asset.quantity += (new_quantity - transaction.quantity)
                transaction.asset.total_spent += (new_total_spent - float(transaction.total_spent))
        # кошельки
            if transaction.order:
                if transaction.wallet.name != wallet_in_base.name:
                    transaction.wallet.money_in_order -= float(transaction.total_spent)
                    wallet_in_base.money_in_order += new_total_spent
                    transaction.wallet.name = wallet_in_base.name
                else:
                    transaction.wallet.money_in_order += (new_total_spent - float(transaction.total_spent))
            transaction.price = new_price
            transaction.total_spent = new_total_spent
            transaction.quantity = new_quantity
        if transaction.wallet.name != wallet_in_base.name:
            transaction.wallet_id = wallet_in_base.id

    db.session.commit()
    return redirect(url_for('asset_info', market_id=market_id, portfolio_url=portfolio_url, asset_url=asset_in_base.ticker.id))

@app.route('/<string:market_id>/<string:portfolio_url>/transaction_delete', methods=['POST'])
@login_required
def transaction_delete(market_id, portfolio_url):
    ''' Удаление транзакции '''
    transaction = db.session.execute(db.select(Transaction).filter_by(id=request.form['id'])).scalar()
    asset_in_base = db.session.execute(db.select(Asset).filter_by(id=transaction.asset_id)).scalar()
    if transaction.order:
        wallet_in_base = db.session.execute(db.select(Wallet).filter_by(id=transaction.wallet_id)).scalar()
        wallet_in_base.money_in_order -= float(transaction.total_spent)
        # удаляем уведомление
        alert_in_base = db.session.execute(db.select(Alert).filter_by(asset_id=asset_in_base.id, price=transaction.price)).scalar()
        if alert_in_base:
            update_alerts_redis(alert_in_base.id)
        db.session.delete(alert_in_base)
    else:
        asset_in_base.quantity -= transaction.quantity
        asset_in_base.total_spent -= transaction.total_spent
    db.session.delete(transaction)
    db.session.commit()
    return redirect(url_for('asset_info', market_id=market_id, portfolio_url=portfolio_url, asset_url=asset_in_base.ticker.id))

@app.route('/<string:market_id>/<string:portfolio_url>/order_to_transaction', methods=['POST'])
@login_required
def order_to_transaction(market_id, portfolio_url):
    ''' Конвертация ордера в транзакцию '''
    transaction = db.session.execute(db.select(Transaction).filter_by(id=request.form['id'])).scalar()
    transaction.order = 0
    transaction.date = request.form['date']
    transaction.asset.quantity += transaction.quantity
    transaction.asset.total_spent += float(transaction.total_spent)
    transaction.wallet.money_in_order -= float(transaction.total_spent)

    # удаление уведомления
    alert_in_base = db.session.execute(db.select(Alert).filter_by(asset_id=transaction.asset_id, price=transaction.price)).scalar()
    if alert_in_base:
        alert_delete_def(id=alert_in_base.id)
    db.session.commit()
    return redirect(url_for('asset_info', market_id=market_id, portfolio_url=portfolio_url, asset_url=transaction.asset.ticker.id))


@app.route('/wallets', methods=['GET'])
@login_required
def wallets():
    ''' Страница кошельков, где хранятся активы '''
    session['last_url'] = request.url
    price_list = price_list_def()
    user = db.session.execute(db.select(User).filter_by(id=current_user.id)).scalar()
    wallets = tuple(user.wallets)
    holder_list = {}
    total_spent = 0

    for portfolio in user.portfolios:
        for asset in portfolio.assets:
            for transaction in asset.transactions:
                if not transaction.order:
                    holder_list[transaction.wallet.name] = float(holder_list.setdefault(transaction.wallet.name, 0)) + float(transaction.quantity) * float(price_list[transaction.asset.ticker.id])
                    total_spent += transaction.total_spent

    return render_template('wallets.html', wallets=tuple(wallets), holder_list=holder_list, total_spent=total_spent)

@app.route('/wallets/add', methods=['POST'])
@login_required
def wallet_add():
    ''' Добавление и изменение кошелька '''
    if request.form['action'] == 'add':
        wallet = Wallet(
            name=request.form['name'],
            money_all=request.form['money_all'] if request.form['money_all'] else 0,
            money_in_order=0,
            user_id=current_user.id
        )
        wallet_in_base = db.session.execute(db.select(Wallet).filter_by(name=wallet.name, user_id=current_user.id)).scalar()
        if not wallet_in_base:
            db.session.add(wallet)
            db.session.commit()
    if request.form['action'] == 'update':
        wallet_in_base = db.session.execute(db.select(Wallet).filter_by(id=request.form['id'])).scalar()
        new_name = request.form['name']
        new_money_all = request.form['money_all'] if request.form['money_all'] else 0
        if new_name != wallet_in_base.name or new_money_all != wallet_in_base.money_all:
            wallet_in_base.name = new_name
            wallet_in_base.money_all = new_money_all
            db.session.commit()

    return redirect(url_for('wallets'))

@app.route('/wallets/delete', methods=['POST'])
@login_required
def wallet_delete():
    ''' Удаление кошелька '''
    wallet_in_base = db.session.execute(db.select(Wallet).filter_by(id=request.form['id'])).scalar()
    if not (wallet_in_base.money_all > 0 or wallet_in_base.transactions):
        db.session.delete(wallet_in_base)
        db.session.commit()
    return redirect(url_for('wallets'))

@app.route('/wallets/in_out', methods=['POST'])
@login_required
def wallet_in_out():
    ''' Внешний ввод вывод на кошелек '''
    wallet_in_base = db.session.execute(db.select(Wallet).filter_by(id=request.form['wallet_id'])).scalar()
    type = request.form['type']
    transfer_amount = float(request.form['transfer_amount']) if type == 'Ввод' else -1 * float(request.form['transfer_amount'])
    wallet_in_base.money_all += transfer_amount
    db.session.commit()
    return redirect(url_for('wallets'))

@app.route('/wallets/transfer', methods=['POST'])
@login_required
def wallet_transfer():
    ''' Перевод с кошелька на кошелек '''
    if request.form['type'] == 'Перевод':
        transfer_amount = float(request.form['transfer_amount'])
        wallet_out_in_base = db.session.execute(db.select(Wallet).filter_by(id=request.form['wallet_out'])).scalar()
        wallet_input_in_base = db.session.execute(db.select(Wallet).filter_by(id=request.form['wallet_in'])).scalar()
        wallet_out_in_base.money_all -= transfer_amount
        wallet_input_in_base.money_all += transfer_amount
        db.session.commit()
    return redirect(url_for('wallets'))

@app.route('/wallets/<string:wallet_name>')
@login_required
def wallet_info(wallet_name):
    ''' Страница кошелька '''
    session['last_url'] = request.url
    price_list = price_list_def()
    user = db.session.execute(db.select(User).filter_by(id=current_user.id)).scalar()
    wallet = db.session.execute(db.select(Wallet).filter_by(name=wallet_name, user_id=current_user.id)).scalar()
    assets_list = {}
    wallet_cost_now = 0.0

    for portfolio in user.portfolios:
        for asset in portfolio.assets:
            for transaction in asset.transactions:
                if assets_list.get(transaction.asset.ticker_id):
                    if transaction.order:
                        assets_list[transaction.asset.ticker_id]['order'] = float(assets_list[transaction.asset.ticker_id].setdefault('order', 0)) + float(transaction.total_spent)
                    else:
                        assets_list[transaction.asset.ticker_id]['quantity'] = float(assets_list[transaction.asset.ticker_id].setdefault('quantity', 0)) + float(transaction.quantity)
                else:
                    assets_list[transaction.asset.ticker_id] = dict(order=float(transaction.total_spent), quantity=0.0) if transaction.order else dict(quantity=float(transaction.quantity), order=0.0)
                    assets_list[transaction.asset.ticker_id]['name'] = transaction.asset.ticker.name
                    assets_list[transaction.asset.ticker_id]['symbol'] = transaction.asset.ticker.symbol
                wallet_cost_now += float(transaction.quantity) * price_list[transaction.asset.ticker_id]

    return render_template('wallet_info.html', wallet=wallet, assets_list=assets_list, price_list=price_list, wallet_cost_now=wallet_cost_now)


@app.route('/tracking_list/<string:market_id>', methods=['GET'])
@login_required
def tracking_list(market_id):
    ''' Страница списка отслеживания '''
    session['last_url'] = request.url
    tickers_in_base = tuple(db.session.execute(db.select(Ticker).filter_by(market_id=market_id)).scalars())
    tracked_tickers = tuple(db.session.execute(db.select(Trackedticker).filter_by(user_id=current_user.id)).scalars())

    # для запрета удаления тикера, если есть ордер
    orders = []
    for ticker in tracked_tickers:
        for alert in ticker.alerts:
            if alert.comment == 'Ордер':
                orders.append(ticker.ticker_id)
    return render_template('tracking_list.html', tickers=tickers_in_base, tracked_tickers=tracked_tickers, orders=orders)


@app.route('/tracking_list/add/<string:ticker_id>', methods=['GET'])
def tracking_list_add_ticker(ticker_id):
    ''' Добавление актива в список отслеживания '''
    ticker_in_base = db.session.execute(db.select(Ticker).filter_by(id=ticker_id)).scalar()
    if ticker_in_base:
        tracked_ticker_in_base = db.session.execute(db.select(Trackedticker).filter_by(ticker_id=ticker_id, user_id=current_user.id)).scalar()
        if not tracked_ticker_in_base:
            tracked_ticker = Trackedticker(ticker_id=ticker_in_base.id, user_id=current_user.id)
            db.session.add(tracked_ticker)
            db.session.commit()
    return redirect(url_for('tracked_ticker_info', market_id=ticker_in_base.market_id, ticker_id=ticker_id))


@app.route('/tracking_list/delete/<string:ticker_id>', methods=['GET'])
def tracking_list_delete_ticker(ticker_id):
    ''' Удаление актива из списка отслеживания '''
    tracked_ticker_in_base = db.session.execute(db.select(Trackedticker).filter_by(id=ticker_id)).scalar()
    if tracked_ticker_in_base:
        # удаляем уведомления
        if tracked_ticker_in_base.alerts != ():
            not_worked_alerts = pickle.loads(redis.get('not_worked_alerts'))
            worked_alerts = pickle.loads(redis.get('worked_alerts'))

            for alert in tracked_ticker_in_base.alerts:
                not_worked_alerts.pop(alert.id, None)
                worked_alerts[current_user.id].pop(alert.id, None)
                db.session.delete(alert)

            redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))
            redis.set('worked_alerts', pickle.dumps(worked_alerts))

        db.session.delete(tracked_ticker_in_base)
        db.session.commit()
    return redirect(session['last_url'])


@app.route('/tracking_list/<string:market_id>/<string:ticker_id>')
@login_required
def tracked_ticker_info(market_id, ticker_id):
    ''' Страница уведомлений актива '''
    session['last_url'] = request.url
    tracked_ticker = db.session.execute(db.select(Trackedticker).filter_by(ticker_id=ticker_id, user_id=current_user.id)).scalar()
    price_list = price_list_def()
    price = price_list[tracked_ticker.ticker_id]
    return render_template('tracked_ticker_info.html', tracked_ticker=tracked_ticker, price=price)


@app.route('/tracking_list/alert_add', methods=['POST'])
def alert_add():
    ''' Добавление уведомления '''
    alert = Alert(
        price=request.form['price'].replace(',', '.'),
        date=date,
        comment=request.form['comment']
    )
    # уведомление пришло из списка отслеживания
    if request.form.get('tracked_ticker_id'):
        tracked_ticker_in_base = db.session.execute(db.select(Trackedticker).filter_by(id=request.form.get('tracked_ticker_id'))).scalar()
        alert.trackedticker_id = tracked_ticker_in_base.id
        ticker_id = tracked_ticker_in_base.ticker_id
    # уведомление пришло из портфеля
    if request.form.get('asset_id'):
        asset_in_base = db.session.execute(db.select(Asset).filter_by(id=request.form.get('asset_id'))).scalar()
        alert.asset_id = asset_in_base.id
        ticker_id = asset_in_base.ticker_id

        tracked_ticker_in_base = db.session.execute(db.select(Trackedticker).filter_by(ticker_id=ticker_id, user_id=current_user.id)).scalar()
        if not tracked_ticker_in_base:
            tracked_ticker = Trackedticker(ticker_id=ticker_id, user_id=current_user.id)
            db.session.add(tracked_ticker)
            db.session.commit()
            alert.trackedticker_id = tracked_ticker.id
        else:
            alert.trackedticker_id = tracked_ticker_in_base.id


    price_list = price_list_def()
    price = price_list[ticker_id]
    alert.type = 'down' if float(price) > float(alert.price) else 'up'

    db.session.add(alert)
    db.session.commit()

    # добавление уведомления в список
    not_worked_alerts = pickle.loads(redis.get('not_worked_alerts'))
    not_worked_alerts[alert.id] = {}
    not_worked_alerts[alert.id]['type'] = alert.type
    not_worked_alerts[alert.id]['price'] = alert.price
    not_worked_alerts[alert.id]['ticker_id'] = ticker_id
    redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))

    return redirect(session['last_url'])


@app.route('/tracking_list/alert_delete', methods=['POST'])
def alert_delete():
    alert_delete_def(id=request.form.get('id'))

    return redirect(session['last_url'])

def alert_delete_def(id=None):
    alert_in_base = db.session.execute(db.select(Alert).filter_by(id=id)).scalar()
    update_alerts_redis(alert_in_base.id)
    if alert_in_base:
        update_alerts_redis(alert_in_base.id)
        need_del_ticker = True

        for alert in alert_in_base.trackedticker.alerts:
            if alert.id != alert_in_base.id:
                need_del_ticker = False
                break

        if not alert_in_base.asset_id:
            session['last_url'] = session['last_url'].replace(('/' + alert_in_base.trackedticker.ticker_id), '')
        if need_del_ticker:
            db.session.delete(alert_in_base.trackedticker)
        db.session.delete(alert_in_base)
        db.session.commit()

def update_alerts_redis(alert_id):
    not_worked_alerts = pickle.loads(redis.get('not_worked_alerts')) if redis.get('not_worked_alerts') else {}
    not_worked_alerts.pop(alert_id, None)
    redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))

    worked_alerts = pickle.loads(redis.get('worked_alerts')) if redis.get('worked_alerts') else {}
    if worked_alerts != {}:
        for i in worked_alerts[current_user.id]:
            if i['id'] == alert_id:
                worked_alerts[current_user.id].remove(i)
                break
        redis.set('worked_alerts', pickle.dumps(worked_alerts))

@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).filter_by(id=user_id)).scalar()

@app.route('/login', methods=['GET', 'POST'])
def login():
    session['last_url'] = request.url
    email = request.form.get('email')
    password = request.form.get('password')

    if request.method == 'POST':
        if email and password:
            user = db.session.execute(db.select(User).filter_by(email=email)).scalar()

            if user and check_password_hash(user.password, password):
                login_user(user, remember=request.form.get('remember-me'))
                next_page = request.args.get('next') if request.args.get('next') else '/'
                new_visit()
                return redirect(next_page)
            else:
                flash('Некорректные данные')
        else:
            flash('Введите данные')

    return render_template('login.html')
@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    email = request.form.get('email')
    password = request.form.get('password')
    password2 = request.form.get('password2')
    if request.method == 'POST':
        if not (email and password and password2):
            flash('Пожалуйста заполните все поля')
        elif db.session.execute(db.select(User).filter_by(email=email)).scalar():
            flash('Такой адрес почты уже используется')
        elif password != password2:
            flash('Пароли не совпадают')
        else:
            hash_password = generate_password_hash(password)
            new_user = User(email=email, password=hash_password)
            db.session.add(new_user)
            db.session.commit()
            # кошелек
            wallet = Wallet(name='Default', money_all=0, money_in_order=0, user_id=new_user.id)
            db.session.add(wallet)
            db.session.commit()

            return redirect(url_for('login'))

        return redirect(url_for('register'))

    else:
        return render_template('register.html')
@app.after_request
def redirect_to_signin(response):
    if response.status_code == 401:
        return redirect(url_for('login') + '?next=' + request.url)

    return response

@app.route('/user/delete')
def user_delete():
    user = db.session.execute(db.select(User).filter_by(id=current_user.id)).scalar()

    not_worked_alerts = pickle.loads(redis.get('not_worked_alerts'))
    worked_alerts = pickle.loads(redis.get('worked_alerts'))

    # alerts
    for ticker in user.trackedtickers:
        for alert in ticker.alerts:
            not_worked_alerts.pop(alert.id, None)
            db.session.delete(alert)
        db.session.delete(ticker)
    worked_alerts.pop(user.id, None)

    # commit redis
    redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))
    redis.set('worked_alerts', pickle.dumps(worked_alerts))

    # wallets
    for walllet in user.wallets:
        db.session.delete(walllet)

    # portfolios, assets, transactions
    for portfolio in user.portfolios:
        if portfolio.assets:
            for asset in portfolio.assets:
                for transaction in asset.transactions:
                    db.session.delete(transaction)
                db.session.delete(asset)
        elif portfolio.other_assets:
            for asset in portfolio.other_assets:
                for body in asset.bodys:
                    db.session.delete(body)
                for operation in asset.operations:
                    db.session.delete(operation)
                db.session.delete(asset)
        db.session.delete(portfolio)

    # user
    db.session.delete(user)
    db.session.commit()

    return redirect(url_for('login'))


@app.route("/json/worked_alerts")
def worked_alerts_detail():
    worked_alerts = pickle.loads(redis.get('worked_alerts')).get(current_user.id) if redis.get('worked_alerts') else {}
    return worked_alerts

@app.route("/demo_user")
def demo_user():
    user = db.session.execute(db.select(User).filter_by(email='demo')).scalar()
    login_user(user)
    return redirect(url_for('portfolios'))

@app.route('/<string:market_id>/<string:portfolio_url>/other_asset_body_add', methods=['POST'])
@login_required
def other_asset_body_add(market_id, portfolio_url):
    ''' Добавление или изменение тела актива '''
    asset_in_base = db.session.execute(db.select(otherAsset).filter_by(id=request.form['asset_id'])).scalar()

    new_body = otherAssetBody(
        name=request.form['name'],
        asset_id=request.form['asset_id'],
        total_spent=request.form['total_spent'].replace(',', '.'),
        cost_now=request.form.get('cost_now').replace(',', '.') if request.form.get('cost_now') else request.form['total_spent'].replace(',', '.'),
        comment=request.form['comment'],
        date=request.form['date']
    )
    # Изменение старого
    if request.form.get('id'):
        asset_body_in_base = db.session.execute(db.select(otherAssetBody).filter_by(id=request.form['id'])).scalar()
        asset_body_in_base.name = new_body.name
        asset_body_in_base.total_spent = new_body.total_spent
        asset_body_in_base.cost_now = new_body.cost_now
        asset_body_in_base.comment = new_body.comment
        asset_body_in_base.date = new_body.date
    else:
        db.session.add(new_body)

    db.session.commit()
    return redirect(url_for('asset_info', market_id=market_id, portfolio_url=portfolio_url, asset_url=asset_in_base.url))


@app.route('/<string:market_id>/<string:portfolio_url>/other_asset_operation_add', methods=['POST'])
@login_required
def other_asset_operation_add(market_id, portfolio_url):
    ''' Добавление или изменение операции актива '''
    asset_in_base = db.session.execute(db.select(otherAsset).filter_by(id=request.form['asset_id'])).scalar()
    new_operation = otherAssetOperation(
        asset_id=request.form['asset_id'],
        total_spent=request.form['total_spent'].replace(',', '.'),
        type=request.form['type'],
        comment=request.form['comment'],
        date=request.form['date']
    )
    # Изменение существующей операции
    if request.form.get('id'):
        asset_operation = db.session.execute(db.select(otherAssetOperation).filter_by(id=request.form['id'])).scalar()
        asset_operation.total_spent = new_operation.total_spent
        asset_operation.type = new_operation.type
        asset_operation.comment = new_operation.comment
        asset_operation.date = new_operation.date
    else:
        db.session.add(new_operation)

    db.session.commit()
    return redirect(url_for('asset_info', market_id=market_id, portfolio_url=portfolio_url, asset_url=asset_in_base.url))

@app.route('/<string:market_id>/<string:portfolio_url>/other_asset_delete', methods=['POST'])
@login_required
def other_asset_delete(market_id, portfolio_url):
    ''' Удаление транзакции '''
    if request.form.get('type') == 'asset_body':
        asset_body = db.session.execute(db.select(otherAssetBody).filter_by(id=request.form.get('id'))).scalar()
        db.session.delete(asset_body)
    if request.form.get('type') == 'asset_operation':
        asset_operation = db.session.execute(db.select(otherAssetOperation).filter_by(id=request.form.get('id'))).scalar()
        db.session.delete(asset_operation)
    if request.form.get('type') == 'asset':
        asset = db.session.execute(db.select(otherAsset).filter_by(id=request.form.get('id'))).scalar()
        if asset.bodys:
            for body in asset.bodys:
                db.session.delete(body)
        if asset.operations:
            for operation in asset.operations:
                db.session.delete(operation)
        session['last_url'] = session['last_url'].replace(('/other/' + asset.url), '')
        db.session.delete(asset)

    db.session.commit()
    return redirect(session['last_url'])


def new_visit():
    if current_user.info:
        current_user.last_visit = datetime.now()
    else:
        ip = request.headers.get('X-Real-IP')
        url = 'http://ip-api.com/json/' + ip
        response = requests.get(url).json()
        if response.get('status') == 'success':
            user_info = userInfo(
                user_id=current_user.id,
                first_visit=datetime.now(),
                last_visit=datetime.now(),
                country=response.get('country'),
                city=response.get('city')
            )
            db.session.add(user_info)
    db.session.commit()


@app.route('/feedback', methods=['POST'])
def feedback():
    feedback = Feedback(user_id=request.form.get('user_id'), text=request.form.get('text'))
    db.session.add(feedback)
    db.session.commit()
    return redirect(session['last_url'])
