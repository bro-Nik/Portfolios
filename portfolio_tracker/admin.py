from flask import render_template, redirect, url_for, request, flash, session, jsonify, abort
from flask_login import login_user, login_required, logout_user, current_user
import os, json, requests, time
from sqlalchemy import func
from celery.contrib.abortable import AbortableTask
#from celery.result import AsyncResult

from portfolio_tracker.app import app, db, celery
from portfolio_tracker.defs import *
from portfolio_tracker.models import User, Ticker, userInfo, Feedback


glob_crypto_price_task_id = ''
glob_stocks_price_task_id = ''
glob_crypto_tickers_task_id = ''
glob_stocks_tickers_task_id = ''


@app.route('/admin/', methods=['GET'])
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

    user_is_admin()

    return render_template('admin/index.html', crypto_count=0, stocks_count=0,
                           users_count=0, admins_count=0)


def user_is_admin():
    admins_in_base = db.session.execute(db.select(User).filter_by(type='admin')).scalar()
    if admins_in_base:
        if current_user.type != 'admin':
            abort(404)


@app.route('/admin/users', methods=['GET'])
def admin_users():
    users = db.session.execute(db.select(User)).scalars()
    return render_template('admin/users.html', users=users)


@app.route('/admin/tickers', methods=['GET'])
def admin_tickers():
    tickers = db.session.execute(db.select(Ticker)).scalars()
    return render_template('admin/tickers.html', tickers=tickers)


@app.route('/admin/feedback', methods=['GET'])
def admin_feedback():
    messages = db.session.execute(db.select(Feedback)).scalars()
    return render_template('admin/feedback.html', messages=messages)


@app.route('/admin/load_tickers', methods=['GET'])
def admin_load_tickers():
    global glob_crypto_tickers_task_id, glob_stocks_tickers_task_id
    glob_crypto_tickers_task_id = load_crypto_tickers.delay().id
    glob_stocks_tickers_task_id = load_stocks_tickers.delay().id
    admin_update_prices_stop()
    return redirect(url_for('admin_index'))


@app.route('/admin/index_detail', methods=['GET'])
def admin_index_detail():
    def state(task):
        if task.id:
            if task.state in ['WORK', 'RETRY']:
                return 'Работает'
            elif task.state == 'LOADING':
                return 'Загрузка'
            elif task.state == 'REVOKED':
                return 'Остановлено'
            else:
                return task.state
        else:
            return 'Остановлено'

    crypto_tickers_count = db.session.execute(
        db.select([func.count()]).select_from(Ticker).filter_by(market_id='crypto')).scalar()
    stocks_tickers_count = db.session.execute(
        db.select([func.count()]).select_from(Ticker).filter_by(market_id='stocks')).scalar()
    users_count = db.session.execute(db.select([func.count()]).select_from(User)).scalar()
    admins_count = db.session.execute(db.select([func.count()]).select_from(User).filter_by(type='admin')).scalar()

    task_crypto_tickers = load_crypto_tickers.AsyncResult(glob_crypto_tickers_task_id)
    task_stocks_tickers = load_stocks_tickers.AsyncResult(glob_stocks_tickers_task_id)

    task_crypto_price = price_list_crypto_def.AsyncResult(glob_crypto_price_task_id)
    task_stocks_price = price_list_stocks_def.AsyncResult(glob_stocks_price_task_id)

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

def start_update_prices():
    global glob_crypto_price_task_id, glob_stocks_price_task_id
    glob_crypto_price_task_id = price_list_crypto_def.delay().id
    glob_stocks_price_task_id = price_list_stocks_def.delay().id

@app.route('/admin/load_tickers_stop', methods=['GET'])
def admin_load_tickers_stop():
    celery.control.revoke(glob_crypto_tickers_task_id, terminate=True)
    celery.control.revoke(glob_stocks_tickers_task_id, terminate=True)
    return redirect(url_for('admin_index'))


@app.route('/admin/users/user_to_admin/<string:user_id>', methods=['GET'])
def user_to_admin(user_id):
    user_is_admin()
    user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar()
    user.type = 'admin'
    db.session.commit()

    return redirect(url_for('admin_users'))


@app.route('/admin/update_prices', methods=['GET'])
def admin_update_prices():
    start_update_prices()
    return redirect(url_for('admin_index'))


@app.route('/admin/stop', methods=['GET'])
def admin_update_prices_stop():
    celery.control.revoke(glob_crypto_price_task_id, terminate=True)
    celery.control.revoke(glob_stocks_price_task_id, terminate=True)
    return redirect(url_for('admin_index'))

@app.route('/admin/active_tasks', methods=['GET'])
def admin_active_tasks():
    i = celery.control.inspect()
    i.active()
    print(type(i.active()))
    return render_template('admin/active_tasks.html', tasks_list=i.active())

@celery.task(bind=True, default_retry_delay=0, max_retries=None)
def test_task(self):
    if self.is_aborted():
        return
    print('Test task')
    time.sleep(5)
    test_task.retry()
