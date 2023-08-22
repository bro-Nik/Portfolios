import json
import pickle
from datetime import datetime
from flask import render_template, redirect, url_for, request, session, abort
from flask_login import login_required, current_user
from transliterate import slugify

from portfolio_tracker.app import app, db, redis
from portfolio_tracker.models import Portfolio, Asset, Ticker, otherAsset, \
        otherAssetOperation, otherAssetBody, Wallet, Transaction, Alert, \
        User
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


