from celery.result import AsyncResult
from flask import render_template, redirect, url_for, request, flash, session, jsonify, abort
from flask_login import login_user, login_required, logout_user, current_user
import os, json, requests, time
from sqlalchemy import func
from celery.contrib.abortable import AbortableTask
#from celery.result import AsyncResult

from portfolio_tracker.app import app, db, celery
from portfolio_tracker.defs import *
from portfolio_tracker.models import User, Ticker, userInfo, Feedback, Wallet
from portfolio_tracker.wraps import admin_only


@app.route('/admin/', methods=['GET'])
@admin_only
def admin_index():
    demo_user = db.session.execute(db.select(User).filter_by(email='demo')).scalar()
    if not demo_user:
        # demo user
        user = User(email='demo', password='demo')
        db.session.add(user)
        wallet = Wallet(name='Default', money_all=0, money_in_order=0, user_id=1)
        db.session.add(wallet)

        # маркеты
        other = Market(name='Other', id='other')
        db.session.add(other)
        crypto = Market(name='Crypto', id='crypto')
        db.session.add(crypto)
        stocks = Market(name='Stocks', id='stocks')
        db.session.add(stocks)
        db.session.commit()

    return render_template('admin/index.html', crypto_count=0, stocks_count=0, users_count=0, admins_count=0)


@app.route('/admin/index_detail', methods=['GET'])
@admin_only
def admin_index_detail():
    def state(task):
        if task.id:
            if task.state in ['WORK']:
                return 'Работает'
            elif task.state in ['RETRY']:
                return 'Ожидает'
            elif task.state == 'LOADING':
                return 'Загрузка'
            elif task.state == 'REVOKED':
                return 'Остановлено'
            elif task.state == 'SUCCESS':
                return 'Готово'
            elif task.state == 'FAILURE':
                return 'Ошибка'
            else:
                return task.state
        else:
            return 'Остановлено'

    crypto_tickers_count = db.session.execute(db.select(func.count()).select_from(Ticker).filter_by(market_id='crypto')).scalar()
    stocks_tickers_count = db.session.execute(
        db.select(func.count()).select_from(Ticker).filter_by(market_id='stocks')).scalar()
    users_count = db.session.execute(db.select(func.count()).select_from(User)).scalar()
    admins_count = db.session.execute(db.select(func.count()).select_from(User).filter_by(type='admin')).scalar()

    crypto_tickers_task_id = redis.get('crypto_tickers_task_id').decode() if redis.get('crypto_tickers_task_id') else ''
    stocks_tickers_task_id = redis.get('stocks_tickers_task_id').decode() if redis.get('stocks_tickers_task_id') else ''
    task_crypto_tickers = AsyncResult(crypto_tickers_task_id)
    task_stocks_tickers = AsyncResult(stocks_tickers_task_id)

    crypto_price_task_id = redis.get('crypto_price_task_id').decode() if redis.get('crypto_price_task_id') else ''
    stocks_price_task_id = redis.get('stocks_price_task_id').decode() if redis.get('stocks_price_task_id') else ''
    task_crypto_price = AsyncResult(crypto_price_task_id)
    task_stocks_price = AsyncResult(stocks_price_task_id)

    when_update_crypto = when_updated_def(redis.get('update-crypto').decode()) if redis.get('update-crypto') else '-'
    when_update_stocks = when_updated_def(redis.get('update-stocks').decode()) if redis.get('update-stocks') else '-'

    return {
        "crypto_tickers_count": crypto_tickers_count,
        "stocks_tickers_count": stocks_tickers_count,
        "users_count": users_count,
        "admins_count": admins_count,

        "task_crypto_tickers_id": task_crypto_tickers.id,
        "task_crypto_tickers_state": state(task_crypto_tickers),
        "task_stocks_tickers_id": task_stocks_tickers.id,
        "task_stocks_tickers_state": state(task_stocks_tickers),

        "task_crypto_price_id": task_crypto_price.id,
        "task_crypto_price_state": state(task_crypto_price),
        "task_stocks_price_id": task_stocks_price.id,
        "task_stocks_price_state": state(task_stocks_price),

        "when_update_crypto": when_update_crypto,
        "when_update_stocks": when_update_stocks
    }


@app.route('/admin/users', methods=['GET'])
@admin_only
def admin_users():
    users = db.session.execute(db.select(User)).scalars()
    return render_template('admin/users.html', users=users)


@app.route('/admin/users/user_to_admin/<string:user_id>', methods=['GET'])
@admin_only
def user_to_admin(user_id):
    user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar()
    user.type = 'admin'
    db.session.commit()
    return redirect(url_for('admin_users'))


@app.route('/admin/tickers', methods=['GET'])
@admin_only
def admin_tickers():
    tickers = db.session.execute(db.select(Ticker)).scalars()
    return render_template('admin/tickers.html', tickers=tickers)


@app.route('/admin/load_tickers', methods=['GET'])
@admin_only
def admin_load_tickers():
    redis.set('crypto_tickers_task_id', str(load_crypto_tickers.delay().id))
    redis.set('stocks_tickers_task_id', str(load_stocks_tickers.delay().id))

    stop_update_prices()
    return redirect(url_for('admin_index'))


@app.route('/admin/load_tickers_stop', methods=['GET'])
@admin_only
def admin_load_tickers_stop():
    if redis.get('crypto_tickers_task_id'):
        celery.control.revoke(redis.get('crypto_tickers_task_id').decode(), terminate=True)
    if redis.get('stocks_tickers_task_id'):
        celery.control.revoke(redis.get('stocks_tickers_task_id').decode(), terminate=True)

    return redirect(url_for('admin_index'))


@app.route('/admin/feedback', methods=['GET'])
@admin_only
def admin_feedback():
    messages = db.session.execute(db.select(Feedback)).scalars()
    return render_template('admin/feedback.html', messages=messages)


@app.route('/admin/active_tasks', methods=['GET'])
@admin_only
def admin_active_tasks():
    i = celery.control.inspect()
    tasks_list = i.active()
    scheduled = i.scheduled()

    return render_template('admin/active_tasks.html', tasks_list=tasks_list, scheduled=scheduled)


@app.route('/admin/del_tasks', methods=['GET'])
@admin_only
def admin_del_tasks():
    delete_tasks()
    return redirect(url_for('admin_index'))


@app.route('/admin/update_prices', methods=['GET'])
@admin_only
def admin_update_prices():
    start_update_prices()
    return redirect(url_for('admin_index'))


@app.route('/admin/stop', methods=['GET'])
@admin_only
def admin_update_prices_stop():
    stop_update_prices()
    return redirect(url_for('admin_index'))


def delete_tasks():
    keys = ['crypto_price_task_id', 'stocks_price_task_id', 'alerts_task_id']
    redis.delete(*keys)
    k = redis.keys('celery-task-meta-*')
    if k:
        redis.delete(*k)


def start_update_prices():
    redis.set('crypto_price_task_id', str(price_list_crypto_def.delay().id))
    redis.set('stocks_price_task_id', str(price_list_stocks_def.delay().id))
    redis.set('alerts_task_id', str(alerts_update_def.delay().id))


def stop_update_prices():
    crypto_id = redis.get('crypto_price_task_id')
    if crypto_id:
        crypto_id = crypto_id.decode()
        celery.control.revoke(crypto_id, terminate=True)

    stocks_id = redis.get('stocks_price_task_id')
    if stocks_id:
        stocks_id = stocks_id.decode()
        celery.control.revoke(stocks_id, terminate=True)

    alerts_id = redis.get('alerts_task_id')
    if alerts_id:
        alerts_id = alerts_id.decode()
        celery.control.revoke(alerts_id, terminate=True)

    delete_tasks()
