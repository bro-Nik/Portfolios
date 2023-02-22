from flask import render_template, redirect, url_for, request, flash, session
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import requests
import pickle

from portfolio_tracker.app import app, db, login_manager, redis
from portfolio_tracker.models import User, userInfo, Wallet


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


@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).filter_by(id=user_id)).scalar()


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.after_request
def redirect_to_signin(response):
    if response.status_code == 401:
        return redirect(url_for('login') + '?next=' + request.url)

    return response


@app.route('/user/delete')
def user_delete():
    user = db.session.execute(db.select(User).filter_by(id=current_user.id)).scalar()

    not_worked_alerts = pickle.loads(redis.get('not_worked_alerts')) if redis.get('not_worked_alerts') else {}
    worked_alerts = pickle.loads(redis.get('worked_alerts')) if redis.get('worked_alerts') else {}

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


def new_visit():
    if current_user.info:
        current_user.last_visit = datetime.now()
    else:
        ip = request.headers.get('X-Real-IP')
        if not ip:
            ip = '212.96.80.137'
        url = 'http://ip-api.com/json/' + ip
        response = requests.get(url).json()
        if response.get('status') == 'success':
            user_info = userInfo(
                user_id=current_user.id,
                first_visit=datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M'),
                last_visit=datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M'),
                country=response.get('country'),
                city=response.get('city')
            )
            db.session.add(user_info)
    db.session.commit()


@app.route("/demo_user")
def demo_user():
    user = db.session.execute(db.select(User).filter_by(email='demo')).scalar()
    login_user(user)
    return redirect(url_for('portfolios'))
