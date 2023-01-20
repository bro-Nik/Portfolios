from flask import render_template, redirect, url_for, request, flash, session
from transliterate import slugify
import os
import requests

from portfolio_tracker.models import Transaction, Asset, Wallet, Portfolio, Ticker, Market, Alert, Setting
from portfolio_tracker.defs import *


@app.route('/first_start', methods=['GET', 'POST'])
def first_start():
    ''' Страница первого запуска '''
    global settings_list
    if request.method == 'GET':
        return render_template('first_start.html')

    if request.method == 'POST':
        # маркеты
        settings_list['markets'] = {}
        settings_list['update_period'] = {}
        if request.form.get('crypto'):
            crypto = Market(name='Crypto',
                            id='crypto')
            db.session.add(crypto)
            settings_list['markets'][crypto.id] = crypto.name
            # период обновления
            settings_list['update_period'][crypto.id] = 5
            crypto_update_price = Setting(name='crypto',
                                          value=5)
            db.session.add(crypto_update_price)
        if request.form.get('stocks'):
            stocks = Market(name='Stocks',
                            id='stocks')
            db.session.add(stocks)
            settings_list['markets'][stocks.id] = stocks.name
            # период обновления
            settings_list['update_period'][stocks.id] = 0
            stocks_update_price = Setting(name='stocks',
                                          value=0)
            db.session.add(stocks_update_price)
            # API
            settings_list['api_key_polygon'] = request.form.get('api_key_polygon')
            api_key_polygon = Setting(
                name='api_key_polygon',
                value=request.form.get('api_key_polygon')
            )
            db.session.add(api_key_polygon)
        # кошелек
        wallet = Wallet(
            name='Default',
            money_all=0,
            money_in_order=0
        )
        db.session.add(wallet)
        db.session.commit()

        # загрузка тикеров
        if request.form.get('crypto'):
            tickers_load('crypto')
        if request.form.get('stocks'):
            tickers_load('stocks')
        settings_list.pop('first_start')

        return redirect(url_for('portfolios'))

@app.route('/settings')
def settings():
    ''' Страница настроек '''
    return render_template('settings.html')

@app.route('/settings/update', methods=['POST'])
def settings_update():
    ''' Изменение настроек '''
    return redirect(url_for('settings'))

@app.route('/', methods=['GET'])
def portfolios():
    ''' Страница портфелей '''
    if settings_list.get('first_start'):
        return redirect(url_for('first_start'))

    price_list = price_list_def()
    portfolios = tuple(db.session.execute(db.select(Portfolio)).scalars())
    total_spent = cost_now = 0
    total_spent_list = {}
    cost_now_list = {}
    orders_in_portfolio = {}
    if portfolios != ():
        for portfolio in portfolios:
            #if portfolio.market.id == 'crypto':
            for asset in portfolio.assets:
                total_spent += asset.total_spent
                cost_now += (asset.quantity * price_list[asset.ticker.id])
                for transaction in asset.transactions:
                    if not transaction.order:
                        total_spent_list[portfolio.id] = float(total_spent_list.setdefault(portfolio.id, 0)) + float(transaction.total_spent)
                        cost_now_list[portfolio.id] = float(cost_now_list.setdefault(portfolio.id, 0)) + float(transaction.quantity) * float(price_list[asset.ticker.id])
            #if portfolio.market.name == 'stocks':
            #    price_list = price_list_def(portfolio.market_id)
            #    for asset in portfolio.assets:
            #        total_spent += asset.total_spent
            #        cost_now += (asset.quantity * price_list[asset.ticker.id])
            #        for transaction in asset.transactions:
            #            if not transaction.order:
            #                total_spent_list[portfolio.id] = float(total_spent_list.setdefault(portfolio.id, 0)) + float(transaction.total_spent)
            #                cost_now_list[portfolio.id] = float(cost_now_list.setdefault(portfolio.id, 0)) + float(transaction.quantity) * float(price_list[asset.ticker.id])
            # в каких портфелях есть ордера, чтобы не удалить
            for asset in portfolio.assets:
                for transaction in asset.transactions:
                    if transaction.order:
                        orders_in_portfolio[portfolio.id] = True
                        break

    return render_template('portfolios.html', portfolios=portfolios, total_spent=total_spent, cost_now=cost_now, total_spent_list=total_spent_list, cost_now_list=cost_now_list, orders_in_portfolio=orders_in_portfolio, triggered_alerts=all_alerts_list['worked'])

@app.route('/nothing')
def nothing():
    return render_template('404.html')

@app.route('/add', methods=['POST'])
def portfolio_add():
    ''' Добавление и изменение портфеля '''
    portfolio = Portfolio(
        name=request.form['name'],
        comment=request.form['comment'],
        market_id=request.form['market_id']
    )
    text = str(portfolio.name) + '-' + str(portfolio.market_id)
    id = slugify(str(text)) if slugify(str(text)) else text
    portfolio_in_base = db.session.execute(db.select(Portfolio).filter_by(id=id)).scalar()
    if portfolio_in_base:
        if request.form['id']:
            portfolio_in_base.name = portfolio.name
            portfolio.id = id
            portfolio_in_base.comment = portfolio.comment
            db.session.commit()
        else:
            flash('Такое название портфеля уже есть. Допускается повторение названий только на разных рынках (Crypto, Stocks)')
        return redirect(url_for('portfolios'))
    else:
        portfolio.id = id
        db.session.add(portfolio)
        db.session.commit()

        return redirect(url_for('portfolio_info', portfolio_id=portfolio.id))

@app.route('/delete', methods=['POST'])
def portfolio_delete():
    ''' Удаление портфеля '''
    portfolio_in_base = db.session.execute(db.select(Portfolio).filter_by(id=request.form['id'])).scalar()
    if portfolio_in_base:
        db.session.delete(portfolio_in_base)
        db.session.commit()
    return redirect(url_for('portfolios'))

@app.route('/<string:portfolio_id>', methods=['GET'])
def portfolio_info(portfolio_id):
    ''' Страница портфеля '''
    price_list = price_list_def()
    portfolio_in_base = db.session.execute(db.select(Portfolio).filter_by(id=portfolio_id)).scalar()
    if portfolio_in_base:
        tickers_in_base = db.session.execute(db.select(Ticker).filter_by(market=portfolio_in_base.market)).scalars()
        portfolio_cost_now = 0
        for asset in portfolio_in_base.assets:
            portfolio_cost_now += (asset.quantity * price_list[asset.ticker.id])
        return render_template('portfolio_info.html', portfolio=portfolio_in_base, price_list=price_list, portfolio_cost_now=portfolio_cost_now, tickers=tickers_in_base, triggered_alerts=all_alerts_list['worked'])
    else:
        return redirect(url_for('portfolios'))

@app.route('/<string:portfolio_id>/add/<string:ticker_id>', methods=['GET'])
def asset_add(portfolio_id, ticker_id):
    ''' Добавление актива в портфель '''
    asset = Asset(
        portfolio_id=portfolio_id,
        percent=0,
        total_spent=0,
        quantity=0
    )
    ticker_in_base = db.session.execute(db.select(Ticker).filter_by(id=ticker_id)).scalar()
    if ticker_in_base:
        asset_in_portfolio = db.session.execute(db.select(Asset).filter_by(ticker_id=ticker_id, portfolio_id=portfolio_id)).scalar()
        if not asset_in_portfolio:
            asset.ticker_id = ticker_id
            db.session.add(asset)
            db.session.commit()

    return redirect(url_for('asset_info', ticker_id=ticker_id, portfolio_id=portfolio_id))

@app.route('/<string:portfolio_id>/asset_update', methods=['POST'])
def asset_update(portfolio_id):
    ''' Изменение актива '''
    asset_in_base = db.session.execute(db.select(Asset).filter_by(id=request.form.get('id'))).scalar()
    if asset_in_base:
        if request.form.get('percent'):
            asset_in_base.percent = request.form.get('percent')
        if request.form.get('comment'):
            asset_in_base.comment = request.form.get('comment')
        db.session.commit()
    return redirect(url_for('asset_info', ticker_id=asset_in_base.ticker_id, portfolio_id=portfolio_id))

@app.route('/<string:portfolio_id>/asset_delete', methods=['POST'])
def asset_delete(portfolio_id):
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
            # отставляем уведомления
            alert.asset_id = None
            alert.comment = 'Актив удален из портфеля ' + str(asset_in_base.portfolio.name)

        db.session.delete(asset_in_base)
        db.session.commit()
    return redirect(url_for('portfolio_info', portfolio_id=portfolio_id))

@app.route('/<string:portfolio_id>/<string:ticker_id>')
def asset_info(ticker_id, portfolio_id):
    ''' Страница актива в портфеле '''
    portfolio_in_base = db.session.execute(db.select(Portfolio).filter_by(id=portfolio_id)).scalar()
    wallets = db.session.execute(db.select(Wallet)).scalars()
    ticker_in_base = db.session.execute(db.select(Ticker).filter_by(id=ticker_id)).scalar()
    if portfolio_in_base and ticker_in_base:
        asset = db.session.execute(db.select(Asset).filter_by(ticker_id=ticker_in_base.id, portfolio_id=portfolio_in_base.id)).scalar()
    price_list = price_list_def()
    price = price_list[ticker_in_base.id]
    # прайсы обновлены (когда)
    when_updated = when_updated_def(price_list[str('update-' + portfolio_in_base.market_id)])

    return render_template('asset_info.html', asset=asset, price=price, when_updated=when_updated, date=date, wallets=tuple(wallets), portfolio=portfolio_in_base, triggered_alerts=all_alerts_list['worked'])

@app.route('/<string:portfolio_id>/transaction_add', methods=['POST'])
def transaction_add(portfolio_id):
    ''' Добавление или изменение транзакции '''
    global all_alerts_list
    asset_in_base = db.session.execute(db.select(Asset).filter_by(id=request.form['asset_id'])).scalar()
    wallet_in_base = db.session.execute(db.select(Wallet).filter_by(name=request.form['wallet'])).scalar()
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
            #asset_in_base.order += float(transaction.total_spent)
            wallet_in_base = db.session.execute(db.select(Wallet).filter_by(name=request.form['wallet'])).scalar()
            wallet_in_base.money_in_order += float(transaction.total_spent)
            # Добавляем уведомление
            alert = Alert(
                price=transaction.price,
                date=transaction.date,
                comment='Ордер',
                asset_id=transaction.asset_id,
                ticker_id=asset_in_base.ticker_id,
                type='down' if float(price_list[asset_in_base.ticker_id]) > float(transaction.price) else 'up'
            )
            db.session.add(alert)
            db.session.commit()
            # записываем в список уведомлений
            all_alerts_list['not_worked'][alert.id] = {}
            all_alerts_list['not_worked'][alert.id]['type'] = alert.type
            all_alerts_list['not_worked'][alert.id]['price'] = alert.price
            all_alerts_list['not_worked'][alert.id]['ticker_id'] = alert.ticker_id
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
                #transaction.asset.order += (new_total_spent - transaction.total_spent)
                # изменяем уведомление
                alert_in_base = db.session.execute(db.select(Alert).filter_by(asset_id=transaction.asset_id, price=transaction.price)).scalar()
                alert_in_base.price = new_price
                all_alerts_list['not_worked'][alert_in_base.id]['price'] = new_price
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
    return redirect(url_for('asset_info', ticker_id=asset_in_base.ticker.id, portfolio_id=portfolio_id))

@app.route('/<string:portfolio_id>/transaction_delete', methods=['POST'])
def transaction_delete(portfolio_id):
    ''' Удаление транзакции '''
    transaction = db.session.execute(db.select(Transaction).filter_by(id=request.form['id'])).scalar()
    asset_in_base = db.session.execute(db.select(Asset).filter_by(id=transaction.asset_id)).scalar()
    if transaction.order:
        wallet_in_base = db.session.execute(db.select(Wallet).filter_by(id=transaction.wallet_id)).scalar()
        wallet_in_base.money_in_order -= float(transaction.total_spent)
        #asset_in_base.order -= float(transaction.total_spent)
        # удаляем уведомление
        alert_in_base = db.session.execute(db.select(Alert).filter_by(asset_id=asset_in_base.id, price=transaction.price)).scalar()
        if alert_in_base:
            all_alerts_list['worked'].pop(alert_in_base.id, None)
            all_alerts_list['not_worked'].pop(alert_in_base.id, None)
        db.session.delete(alert_in_base)
    else:
        asset_in_base.quantity -= transaction.quantity
        asset_in_base.total_spent -= transaction.total_spent
    db.session.delete(transaction)
    db.session.commit()
    return redirect(url_for('asset_info', ticker_id=asset_in_base.ticker.id, portfolio_id=portfolio_id))

@app.route('/<string:portfolio_id>/order_to_transaction', methods=['POST'])
def order_to_transaction(portfolio_id):
    ''' Конвертация ордера в транзакцию '''
    transaction = db.session.execute(db.select(Transaction).filter_by(id=request.form['id'])).scalar()
    transaction.order = 0
    transaction.date = request.form['date']
    #transaction.asset.order -= float(transaction.total_spent)
    transaction.asset.quantity += transaction.quantity
    transaction.asset.total_spent += float(transaction.total_spent)
    transaction.wallet.money_in_order -= float(transaction.total_spent)
    db.session.add(transaction)
    # удаление уведомления
    alert_in_base = db.session.execute(db.select(Alert).filter_by(asset_id=transaction.asset_id, price=transaction.price)).scalar()
    if alert_in_base:
        all_alerts_list['worked'].pop(alert_in_base.id, None)
        all_alerts_list['not_worked'].pop(alert_in_base.id, None)
        db.session.delete(alert_in_base)
    db.session.commit()
    return redirect(url_for('asset_info', ticker_id=transaction.asset.ticker.id, portfolio_id=portfolio_id))


@app.route('/wallets', methods=['GET'])
def wallets():
    ''' Страница кошельков, где хранятся активы '''
    price_list = price_list_def()
    wallets = tuple(db.session.execute(db.select(Wallet)).scalars())
    holder_list = {}
    total_spent = 0

    markets_in_base = db.session.execute(db.select(Market)).scalars()
    for market in markets_in_base:
        for ticker in market.tickers:
            for asset in ticker.assets:
                for transaction in asset.transactions:
                    if not transaction.order:
                        holder_list[transaction.wallet.name] = float(holder_list.setdefault(transaction.wallet.name, 0)) + float(transaction.quantity) * float(price_list[transaction.asset.ticker.id])
                        total_spent += transaction.total_spent


    return render_template('wallets.html', wallets=tuple(wallets), holder_list=holder_list, total_spent=total_spent, triggered_alerts=all_alerts_list['worked'])

@app.route('/wallets/add', methods=['POST'])
def wallet_add():
    ''' Добавление и изменение кошелька '''
    if request.form['action'] == 'add':
        wallet = Wallet(
            name=request.form['name'],
            money_all=request.form['money_all'] if request.form['money_all'] else 0,
            money_in_order=0
        )
        wallet_in_base = db.session.execute(db.select(Wallet).filter_by(name=wallet.name)).scalar()
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
def wallet_delete():
    ''' Удаление кошелька '''
    wallet_in_base = db.session.execute(db.select(Wallet).filter_by(id=request.form['id'])).scalar()
    if not (wallet_in_base.money_all > 0 or wallet_in_base.transactions):
        db.session.delete(wallet_in_base)
        db.session.commit()
    return redirect(url_for('wallets'))

@app.route('/wallets/in_out', methods=['POST'])
def wallet_in_out():
    ''' Внешний ввод вывод на кошелек '''
    wallet_in_base = db.session.execute(db.select(Wallet).filter_by(name=request.form['wallet'])).scalar()
    type = request.form['type']
    transfer_amount = float(request.form['transfer_amount']) if type == 'Ввод' else -1 * float(request.form['transfer_amount'])
    wallet_in_base.money_all += transfer_amount
    db.session.commit()
    return redirect(url_for('wallets'))

@app.route('/wallets/transfer', methods=['POST'])
def wallet_transfer():
    ''' Перевод с кошелька на кошелек '''
    if request.form['type'] == 'Перевод':
        transfer_amount = float(request.form['transfer_amount'])
        wallet_out_in_base = db.session.execute(db.select(Wallet).filter_by(name=request.form['wallet_out'])).scalar()
        wallet_input_in_base = db.session.execute(db.select(Wallet).filter_by(name=request.form['wallet_in'])).scalar()
        wallet_out_in_base.money_all -= transfer_amount
        wallet_input_in_base.money_all += transfer_amount
        db.session.commit()
    return redirect(url_for('wallets'))

@app.route('/wallets/<string:wallet_name>')
def wallet_info(wallet_name):
    ''' Страница кошелька '''
    price_list = price_list_def()
    wallet = db.session.execute(db.select(Wallet).filter_by(name=wallet_name)).scalar()
    assets_list = {}
    wallet_cost_now = 0.0
    markets_in_base = db.session.execute(db.select(Market)).scalars()

    for market in markets_in_base:
        for ticker in market.tickers:
            for asset in ticker.assets:
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

    return render_template('wallet_info.html', wallet=wallet, assets_list=assets_list, price_list=price_list, wallet_cost_now=wallet_cost_now, triggered_alerts=all_alerts_list['worked'])


@app.route('/alerts/<string:market_id>', methods=['GET'])
def alerts_list(market_id):
    ''' Страница списка отслеживания '''
    tickers_in_base = tuple(db.session.execute(db.select(Ticker).filter_by(market_id=market_id)).scalars())
    # для запрета удаления тикера, если есть ордер
    orders = []
    tickers_in_list = False
    for ticker in tickers_in_base:
        # есть ли уведомления или тикеры в списке отслеживания
        if ticker.alerts or ticker.white_list:
            tickers_in_list = True
        for asset in ticker.assets:
            for transaction in asset.transactions:
                if transaction.order:
                    orders.append(ticker.id)
    return render_template('alerts_list.html', tickers=tickers_in_base, orders=orders, tickers_in_list=tickers_in_list, triggered_alerts=all_alerts_list['worked'])

@app.route('/alerts/add', methods=['POST'])
def alert_add():
    ''' Добавление уведомления '''
    alert = Alert(
        price=request.form['price'].replace(',', '.'),
        date=date,
        comment=request.form['comment']
    )
    # уведомление пришло из списка отслеживания
    if request.form.get('ticker_id'):
        ticker_in_base = db.session.execute(db.select(Ticker).filter_by(id=request.form.get('ticker_id'))).scalar()
        ticker_id = ticker_in_base.id
        market_id = ticker_in_base.market_id
    # уведомление пришло из портфеля
    if request.form.get('asset_id'):
        asset_in_base = db.session.execute(db.select(Asset).filter_by(id=request.form.get('asset_id'))).scalar()
        ticker_id = asset_in_base.ticker_id
        market_id = asset_in_base.ticker.market_id

    alert.ticker_id = ticker_id
    price_list = price_list_def()
    price = price_list[ticker_id]
    alert.type = 'down' if float(price) > float(alert.price) else 'up'

    if 'asset_in_base' in locals():
        if asset_in_base:
            alert.asset_id = asset_in_base.id
            # return redirect(url_for('asset_info', ticker_id=asset_in_base.ticker.id, portfolio_id=asset_in_base.portfolio_id))

    db.session.add(alert)
    db.session.commit()

    # добавление уведомления в список
    all_alerts_list['not_worked'][alert.id] = {}
    all_alerts_list['not_worked'][alert.id]['type'] = alert.type
    all_alerts_list['not_worked'][alert.id]['price'] = alert.price
    all_alerts_list['not_worked'][alert.id]['ticker_id'] = alert.ticker_id

    if 'asset_in_base' in locals():
        return redirect(url_for('asset_info', ticker_id=asset_in_base.ticker.id, portfolio_id=asset_in_base.portfolio_id))
    else:
        return redirect(url_for('ticker_alerts', market_id=ticker_in_base.market.id, ticker_id=ticker_in_base.id))

@app.route('/alerts/add/<string:ticker_id>', methods=['GET'])
def alerts_add_ticker(ticker_id):
    ''' Добавление актива в список отслеживания '''
    ticker_in_base = db.session.execute(db.select(Ticker).filter_by(id=ticker_id)).scalar()
    if ticker_in_base:
        ticker_in_base.white_list = True
        db.session.commit()
    return redirect(url_for('ticker_alerts', market_id=ticker_in_base.market_id, ticker_id=ticker_id))

@app.route('/alerts/delete/<string:ticker_id>', methods=['GET'])
def alerts_delete_ticker(ticker_id):
    ''' Удаление актива из списка отслеживания '''
    ticker_in_base = db.session.execute(db.select(Ticker).filter_by(id=ticker_id)).scalar()
    if ticker_in_base:
        ticker_in_base.white_list = False
        # удаляем уведомления
        if ticker_in_base.alerts != ():
            for alert in ticker_in_base.alerts:
                all_alerts_list['worked'].pop(alert.id, None)
                all_alerts_list['not_worked'].pop(alert.id, None)
                db.session.delete(alert)
        db.session.commit()
    return redirect(url_for('alerts_list', market_id=ticker_in_base.market_id))

@app.route('/alerts/<string:market_id>/<string:ticker_id>')
def alerts_ticker(market_id, ticker_id):
    ''' Страница уведомлений актива '''
    ticker_in_base = db.session.execute(db.select(Ticker).filter_by(id=ticker_id)).scalar()
    price_list = price_list_def()
    price = price_list[ticker_in_base.id]
    return render_template('alerts_ticker.html', ticker=ticker_in_base, price=price, triggered_alerts=all_alerts_list['worked'])

@app.route('/alerts/delete', methods=['POST'])
def alert_delete():
    alert_in_base = db.session.execute(db.select(Alert).filter_by(id=request.form['id'])).scalar()
    # костыль, переделать на request
    ticker_id = alert_in_base.ticker_id
    if alert_in_base.asset:
        portfolio_id = alert_in_base.asset.portfolio_id
    else:
        market_id = alert_in_base.ticker.market_id

    if alert_in_base:
        all_alerts_list['worked'].pop(alert_in_base.id, None)
        all_alerts_list['not_worked'].pop(alert_in_base.id, None)
        db.session.delete(alert_in_base)
        db.session.commit()

    if 'portfolio_id' in locals():
        return redirect(url_for('asset_info', ticker_id=ticker_id, portfolio_id=portfolio_id))
    else:
        return redirect(url_for('alerts_ticker', ticker_id=ticker_id, market_id=market_id))


