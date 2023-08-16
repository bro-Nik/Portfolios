import json
import pickle
from datetime import datetime
from flask import render_template, redirect, url_for, request, session, abort
from flask_login import login_required, current_user
from transliterate import slugify

from portfolio_tracker.app import app, db, redis
from portfolio_tracker.models import Portfolio, Asset, Ticker, otherAsset, \
        otherAssetOperation, otherAssetBody, Wallet, Transaction, Alert, \
        User, Trackedticker, Feedback
from portfolio_tracker.general_functions import price_list_def
from portfolio_tracker.wraps import demo_user_change


@app.route('/settings')
@login_required
def settings():
    """ Settings page """
    return render_template('settings.html')


@app.errorhandler(404)
@login_required
def page_not_found(e):
    return render_template('404.html')



@app.route('/<string:market_id>/<string:portfolio_url>/order_to_transaction',
           methods=['POST'])
@login_required
@demo_user_change
def order_to_transaction(market_id, portfolio_url):
    """ Convert order to transaction """
    transaction = db.session.execute(
            db.select(Transaction).filter_by(id=request.form['id'])).scalar()
    transaction.order = 0
    transaction.date = request.form['date']
    transaction.asset.quantity += transaction.quantity
    transaction.asset.total_spent += float(transaction.total_spent)
    if transaction.type != 'Продажа':
        transaction.wallet.money_in_order -= float(transaction.total_spent)

    # удаление уведомления
    alert_in_base = db.session.execute(
            db.select(Alert).filter_by(asset_id=transaction.asset_id,
                                       price=transaction.price)).scalar()
    if alert_in_base:
        alert_delete_def(id=alert_in_base.id)
    db.session.commit()
    return redirect(url_for('asset_info',
                            market_id=market_id,
                            portfolio_url=portfolio_url,
                            asset_url=transaction.asset.ticker.id))




@app.route('/tracking_list/add/<string:ticker_id>', methods=['GET'])
@demo_user_change
def tracking_list_add_ticker(ticker_id):
    """ Add to Tracking list """
    ticker_in_base = db.session.execute(
            db.select(Ticker).filter_by(id=ticker_id)).scalar()
    if ticker_in_base:
        tracked_ticker_in_base = db.session.execute(
            db.select(Trackedticker).
            filter_by(ticker_id=ticker_id, user_id=current_user.id)).scalar()
        if not tracked_ticker_in_base:
            tracked_ticker = Trackedticker(ticker_id=ticker_in_base.id,
                                           user_id=current_user.id)
            db.session.add(tracked_ticker)
            db.session.commit()
    return redirect(url_for('tracked_ticker_info',
                            market_id=ticker_in_base.market_id,
                            ticker_id=ticker_id))


@app.route('/tracking_list/delete/<string:ticker_id>', methods=['GET'])
@demo_user_change
def tracking_list_delete_ticker(ticker_id):
    """ Delete asset in Tracking list """
    tracked_ticker_in_base = db.session.execute(
            db.select(Trackedticker).filter_by(id=ticker_id)).scalar()
    if tracked_ticker_in_base:
        # удаляем уведомления
        if tracked_ticker_in_base.alerts != ():
            alerts_redis = redis.get('not_worked_alerts')

            not_worked_alerts = pickle.loads(
                    alerts_redis) if alerts_redis else {}

            alerts_redis = redis.get('worked_alerts')
            worked_alerts = pickle.loads(alerts_redis) if alerts_redis else {}

            for alert in worked_alerts[current_user.id]:
                if alert['name'] == tracked_ticker_in_base.ticker.name:
                    worked_alerts[current_user.id].remove(alert)

            for alert in tracked_ticker_in_base.alerts:
                not_worked_alerts.pop(alert.id, None)

                db.session.delete(alert)

            redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))
            redis.set('worked_alerts', pickle.dumps(worked_alerts))

        db.session.delete(tracked_ticker_in_base)
        db.session.commit()
    return redirect(session['last_url'])


@app.route('/tracking_list/<string:market_id>/<string:ticker_id>')
@login_required
def tracked_ticker_info(market_id, ticker_id):
    """ Asset alerts page """
    session['last_url'] = request.url
    tracked_ticker = db.session.execute(
        db.select(Trackedticker).filter_by(ticker_id=ticker_id,
                                           user_id=current_user.id)).scalar()
    price_list = price_list_def()
    price = price_list.get(tracked_ticker.ticker_id)
    price = float(price) if price else 0
    return render_template('tracked_ticker_info.html',
                           tracked_ticker=tracked_ticker,
                           price=price)


@app.route('/tracking_list/alert_add', methods=['POST'])
@login_required
@demo_user_change
def alert_add():
    """ Add alert """
    alert = Alert(
        price=request.form['price'].replace(',', '.'),
        date=datetime.now().date(),
        comment=request.form['comment']
    )
    # уведомление пришло из списка отслеживания
    if request.form.get('tracked_ticker_id'):
        tracked_ticker_in_base = db.session.execute(
            db.select(Trackedticker).
            filter_by(id=request.form.get('tracked_ticker_id'))).scalar()
        alert.trackedticker_id = tracked_ticker_in_base.id
        ticker_id = tracked_ticker_in_base.ticker_id
    # уведомление пришло из портфеля
    else:
        asset_in_base = db.session.execute(
            db.select(Asset).filter_by(id=request.form.get('asset_id'))).scalar()
        alert.asset_id = asset_in_base.id
        ticker_id = asset_in_base.ticker_id

        tracked_ticker_in_base = db.session.execute(
            db.select(Trackedticker).filter_by(ticker_id=ticker_id,
                                               user_id=current_user.id)).scalar()
        if not tracked_ticker_in_base:
            tracked_ticker = Trackedticker(ticker_id=ticker_id,
                                           user_id=current_user.id)
            db.session.add(tracked_ticker)
            db.session.commit()
            alert.trackedticker_id = tracked_ticker.id
        else:
            alert.trackedticker_id = tracked_ticker_in_base.id

    price_list = price_list_def()
    price = price_list[ticker_id] if price_list.get(ticker_id) else '-'
    alert.type = 'down' if float(price) > float(alert.price) else 'up'

    db.session.add(alert)
    db.session.commit()

    # добавление уведомления в список
    alerts_redis = redis.get('not_worked_alerts')
    not_worked_alerts = pickle.loads(alerts_redis) if alerts_redis else {}
    not_worked_alerts[alert.id] = {}
    not_worked_alerts[alert.id]['type'] = alert.type
    not_worked_alerts[alert.id]['price'] = alert.price
    not_worked_alerts[alert.id]['ticker_id'] = ticker_id
    redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))

    return redirect(session['last_url'])


@app.route('/tracking_list/alert_delete', methods=['POST'])
@login_required
@demo_user_change
def alert_delete():
    alert_delete_def(id=request.form.get('id'))
    return redirect(session['last_url'])


def alert_delete_def(id=None):
    alert_in_base = db.session.execute(
            db.select(Alert).filter_by(id=id)).scalar()
    update_alerts_redis(alert_in_base.id)
    if alert_in_base:
        update_alerts_redis(alert_in_base.id)
        need_del_ticker = True

        for alert in alert_in_base.trackedticker.alerts:
            if alert.id != alert_in_base.id:
                need_del_ticker = False
                break

        if not alert_in_base.asset_id and need_del_ticker:
            session['last_url'] = session['last_url'].\
                        replace(('/'
                                + alert_in_base.trackedticker.ticker.market.id
                                + '/'
                                + alert_in_base.trackedticker.ticker_id), '')
        if need_del_ticker:
            db.session.delete(alert_in_base.trackedticker)
        db.session.delete(alert_in_base)
        db.session.commit()


def update_alerts_redis(alert_id):
    alerts_redis = redis.get('not_worked_alerts')
    not_worked_alerts = pickle.loads(alerts_redis) if alerts_redis else {}
    not_worked_alerts.pop(alert_id, None)
    redis.set('not_worked_alerts', pickle.dumps(not_worked_alerts))

    alerts_redis = redis.get('worked_alerts')
    worked_alerts = pickle.loads(alerts_redis) if alerts_redis else {}
    if worked_alerts != {}:
        for i in worked_alerts[current_user.id]:
            if i['id'] == alert_id:
                worked_alerts[current_user.id].remove(i)
                break
        redis.set('worked_alerts', pickle.dumps(worked_alerts))


@app.route("/json/<int:user_id>/worked_alerts")
@login_required
def worked_alerts_detail(user_id):
    alerts = redis.get('worked_alerts')
    worked_alerts = pickle.loads(alerts).get(user_id) if alerts else {}
    if worked_alerts:
        for alert in worked_alerts:
            if alert['link']['source'] == 'portfolio':
                alert['link'] = \
                        url_for('asset_info',
                                market_id=alert['link']['market_id'],
                                portfolio_url=alert['link']['portfolio_url'],
                                asset_url=alert['link']['asset_url'])
            elif alert['link']['source'] == 'tracking_list':
                alert['link'] = url_for('tracked_ticker_info',
                                        market_id=alert['link']['market_id'],
                                        ticker_id=alert['link']['ticker_id'])
    return worked_alerts


@app.route('/<string:market_id>/<string:portfolio_url>/other_asset_body_add',
           methods=['POST'])
@login_required
@demo_user_change
def other_asset_body_add(market_id, portfolio_url):
    """ Add or change body of other asset """
    asset_in_base = db.session.execute(
            db.select(otherAsset).
            filter_by(id=request.form['asset_id'])).scalar()

    total_spent = request.form['total_spent'].replace(',', '.')
    cost_now = request.form.get('cost_now')
    new_body = otherAssetBody(
        name=request.form['name'],
        asset_id=request.form['asset_id'],
        total_spent=total_spent,
        cost_now=cost_now.replace(',', '.') if cost_now else total_spent,
        comment=request.form['comment'],
        date=request.form['date']
    )
    # Изменение старого
    if request.form.get('id'):
        asset_body_in_base = db.session.execute(
                db.select(otherAssetBody).
                filter_by(id=request.form['id'])).scalar()
        asset_body_in_base.name = new_body.name
        asset_body_in_base.total_spent = new_body.total_spent
        asset_body_in_base.cost_now = new_body.cost_now
        asset_body_in_base.comment = new_body.comment
        asset_body_in_base.date = new_body.date
    else:
        db.session.add(new_body)

    db.session.commit()
    return redirect(
        url_for('asset_info',
                market_id=market_id,
                portfolio_url=portfolio_url,
                asset_url=asset_in_base.url))


@app.route('/<string:market_id>/<string:portfolio_url>/other_asset_operation_add',
           methods=['POST'])
@login_required
@demo_user_change
def other_asset_operation_add(market_id, portfolio_url):
    """ Add or change operation of other asset """
    asset_in_base = db.session.execute(
            db.select(otherAsset).
            filter_by(id=request.form['asset_id'])).scalar()
    total_spent = request.form['total_spent'].replace(',', '.')
    type = request.form['type']
    total_spent = total_spent if type == 'Прибыль' else -1 * float(total_spent)
    new_operation = otherAssetOperation(
        asset_id=request.form['asset_id'],
        total_spent=total_spent,
        type=type,
        comment=request.form['comment'],
        date=request.form['date']
    )
    # Изменение существующей операции
    if request.form.get('id'):
        asset_operation = db.session.execute(
                db.select(otherAssetOperation).
                filter_by(id=request.form['id'])).scalar()
        asset_operation.total_spent = new_operation.total_spent
        asset_operation.type = new_operation.type
        asset_operation.comment = new_operation.comment
        asset_operation.date = new_operation.date
    else:
        db.session.add(new_operation)

    db.session.commit()
    return redirect(
        url_for('asset_info',
                market_id=market_id,
                portfolio_url=portfolio_url,
                asset_url=asset_in_base.url))


