import json
from flask import Response, jsonify, render_template, redirect, send_file, url_for, request, flash, session, Blueprint
from flask_babel import gettext
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import requests
import pickle

from portfolio_tracker.app import db, login_manager, redis
from portfolio_tracker.general_functions import float_
from portfolio_tracker.models import Alert, Asset, Portfolio, Transaction, User, WhitelistTicker, userInfo, Wallet
from portfolio_tracker.whitelist.whitelist import get_whitelist_ticker


user = Blueprint('user',
                  __name__,
                  template_folder='templates',
                  static_folder='static')

def get_user(email):
    return db.session.execute(db.select(User).filter_by(email=email)).scalar()


@user.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        password2 = request.form.get('password2')

        if not (email and password and password2):
            flash(gettext('Fill in your Email, password and confirmation password'), 'danger')
        elif get_user(email):
            flash(gettext('This Email address is already in use'), 'danger')
        elif password != password2:
            flash(gettext('Password and confirmation password do not match'), 'danger')
        else:
            hash_password = generate_password_hash(password)
            new_user = User(email=email, password=hash_password)
            db.session.add(new_user)

            new_user.wallets.append(Wallet(name=gettext('Default Wallet')))
            new_user.info.append(userInfo(first_visit=datetime.now()))

            db.session.commit()

            return redirect(url_for('.login'))

    return render_template('user/register.html', locale=get_locale())


@user.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash(gettext('Enter your Email and password'), 'danger')

        user = get_user(email)
        if user and check_password_hash(user.password, password):
            login_user(user, remember=request.form.get('remember-me')) 
            new_visit()
            if request.args.get('next'):
                return redirect(request.args.get('next'))
            else:
                return redirect(url_for('portfolio.portfolios'))
        else:
            flash(gettext('Invalid Email or password'), 'danger')

    return render_template('user/login.html', locale=get_locale())



@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).filter_by(id=user_id)).scalar()


@user.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('.login'))


@user.after_request
def redirect_to_signin(response):
    if response.status_code == 401:
        return redirect(url_for('.login') + '?next=' + request.url)

    return response


@user.route('/user_action', methods=['POST'])
@login_required
def user_action():
    data = json.loads(request.data) if request.data else {}
    action = data.get('action')

    if action == 'delete_user':
        user_delete_def(current_user.id)
        return {'redirect': str(url_for('.login'))}

    elif action == 'delete_data':
        for portfolio in current_user.portfolios:
            for asset in portfolio.assets:
                for transaction in asset.transactions:
                    db.session.delete(transaction)
                db.session.delete(asset)
            db.session.delete(portfolio)
        for wallet in current_user.wallets:
            db.session.delete(wallet)
        for whitelist_ticker in current_user.whitelist_tickers:
            for alert in whitelist_ticker.alerts:
                db.session.delete(alert)
            db.session.delete(whitelist_ticker)

        db.session.add(Wallet(name='Default', user_id=current_user.id))

    db.session.commit()
    flash('Профиль очищен', 'success')

    return ''


def user_delete_def(user_id):
    user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar()

    # alerts
    for ticker in user.whitelist_tickers:
        for alert in ticker.alerts:
            db.session.delete(alert)
        db.session.delete(ticker)

    # wallets
    for walllet in user.wallets:
        db.session.delete(walllet)

    # portfolios, assets, transactions
    for portfolio in user.portfolios:
        for asset in portfolio.assets:
            for transaction in asset.transactions:
                db.session.delete(transaction)
            db.session.delete(asset)

        for asset in portfolio.other_assets:
            for body in asset.bodys:
                db.session.delete(body)
            for operation in asset.operations:
                db.session.delete(operation)
            db.session.delete(asset)
        db.session.delete(portfolio)

    # user info
    if user.info:
        db.session.delete(user.info)
        db.session.commit()

    # user
    db.session.delete(user)
    db.session.commit()


def new_visit():
    time_now = datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M')
    info = False
    ip = request.headers.get('X-Real-IP')
    if ip:
        url = 'http://ip-api.com/json/' + ip
        response = requests.get(url).json()
        if response.get('status') == 'success':
            info = True
    if current_user.info != ():
        current_user.info.last_visit = time_now
        if info:
            current_user.info.country = response.get('country')
            current_user.info.city = response.get('city')
    else:
        user_info = userInfo(
            user_id=current_user.id,
            first_visit=time_now,
            last_visit=time_now,
            country=response.get('country') if info else None,
            city=response.get('city') if info else None
        )
        db.session.add(user_info)
    db.session.commit()


@user.route("/demo_user")
def demo_user():
    user = db.session.execute(db.select(User).filter_by(email='demo@demo')).scalar()
    login_user(user)
    return redirect(url_for('portfolio.portfolios'))


@user.route('/settings_profile')
@login_required
def settings_profile():
    """ Settings page """
    return render_template('user/settings_profile.html', locale=get_locale())


@user.route('/settings_export_import', methods=['GET'])
@login_required
def settings_export_import():
    return render_template('user/settings_export_import.html')


@user.route('/export', methods=['GET'])
@login_required
def export_data():
    result = {'wallets': [],
              'portfolios': [],
              'whitelist_tickers': []}

    for wallet in current_user.wallets:
        result['wallets'].append({'id': wallet.id,
                                  'name': wallet.name,
                                  'money_all': wallet.money_all})


    for portfolio in current_user.portfolios:
        p = {'market_id': portfolio.market_id,
             'name': portfolio.name,
             'comment': portfolio.comment,
             'assets': []}

        for asset in portfolio.assets:
            a = {'ticker_id': asset.ticker_id,
                 'percent': asset.percent,
                 'comment': asset.comment,
                 'transactions': [],
                 'alerts': []}

            for transaction in asset.transactions:
                a['transactions'].append({
                    'date': transaction.date,
                    'quantity': transaction.quantity,
                    'price': transaction.price,
                    'total_spent': transaction.total_spent,
                    'type': transaction.type,
                    'comment': transaction.comment,
                    'wallet_id': transaction.wallet_id,
                    'order': transaction.order
                })

            for alert in asset.alerts:
                if alert.transaction:
                    continue

                a['alerts'].append({
                    'date': alert.date,
                    'ticker_id': alert.whitelist_ticker.ticker_id,
                    'price': alert.price,
                    'type': alert.type,
                    'comment': alert.comment,
                    'status': alert.status
                })

            p['assets'].append(a)

        result['portfolios'].append(p)

    for whitelist_ticker in current_user.whitelist_tickers:
        alerts = []
        for alert in whitelist_ticker.alerts:
            if alert.asset_id:
                continue

            alerts.append({
                'date': alert.date,
                'price': alert.price,
                'type': alert.type,
                'comment': alert.comment,
                'status': alert.status
            })

        if alerts:
            result['whitelist_tickers'].append({
                'ticker_id': whitelist_ticker.ticker_id,
                'comment': whitelist_ticker.comment,
                'alerts': alerts
            })

    filename = 'portfolios_export (' + str(datetime.now().date()) +').txt'
    return Response(json.dumps(result),
                    mimetype='application/json',
		            headers={'Content-disposition': 'attachment; filename=' + filename})


@user.route('/import_post', methods=['POST'])
@login_required
def import_data_post():
    try:
        data = json.loads(request.form['import'])
    except:
        flash('Данные не могут конвертироваться', 'danger')
        return redirect(url_for('.settings_export_import'))

    def get_new_wallet_id(old_id):
        for wallet in data['wallets']:
            if old_id == wallet['id']:
                return int(wallet['new_id'])
        return None


    for wallet in data['wallets']:
        new_wallet = Wallet(user_id=current_user.id,
                            name=wallet['name'],
                            money_all=wallet['money_all'])
        db.session.add(new_wallet)
        db.session.commit()
        wallet['new_id'] = new_wallet.id


    for portfolio in data['portfolios']:
        new_portfolio = Portfolio(user_id=current_user.id,
                                  market_id=portfolio['market_id'],
                                  name=portfolio['name'],
                                  comment=portfolio['comment'])
        db.session.add(new_portfolio)

        for asset in portfolio['assets']:
            new_asset = Asset(ticker_id=asset['ticker_id'],
                              percent=float_(asset['percent'], 0),
                              comment=asset['comment'])
            new_portfolio.assets.append(new_asset)

            for transaction in asset['transactions']:
                new_transaction = Transaction(
                    date=transaction['date'],
                    quantity=transaction['quantity'],
                    price=transaction['price'],
                    total_spent=transaction['total_spent'],
                    type=transaction['type'],
                    comment=transaction['comment'],
                    wallet_id=get_new_wallet_id(transaction['wallet_id']),
                    order=transaction['order']
                    )
                new_asset.transactions.append(new_transaction)

                if new_transaction.order:
                    ticker = get_whitelist_ticker(new_transaction.asset.ticker_id, True)
                    new_transaction.alert.append(Alert(
                        asset_id=new_transaction.asset_id,
                        date=new_transaction.date,
                        whitelist_ticker_id=ticker.id,
                        price=new_transaction.price,
                        type='down' if new_transaction.type == 'buy' else 'up',
                        status='on'
                    ))


            for alert in asset['alerts']:
                ticker = get_whitelist_ticker(alert['ticker_id'], True)
                new_alert = Alert(
                    date=alert['date'],
                    whitelist_ticker_id=ticker.id,
                    price=alert['price'],
                    type=alert['type'],
                    comment=alert['comment'],
                    status=alert['status']
                    )
                new_asset.alerts.append(new_alert)

    db.session.commit()


    for whitelist_ticker in data['whitelist_tickers']:
        new_ticker = get_whitelist_ticker(whitelist_ticker.get('ticker_id'), True)
        new_ticker.comment = whitelist_ticker.get('comment', '')
        
        for alert in whitelist_ticker.get('alerts'):
            new_alert = Alert(
                date=alert.get('date'),
                price=alert.get('price'),
                type=alert.get('type'),
                comment=alert.get('comment'),
                status=alert.get('status')
                )
            new_ticker.alerts.append(new_alert)
            
    db.session.commit()

    flash('Импорт выполнен', 'success')

    return redirect(url_for('.settings_export_import'))


def get_locale():
    if current_user.is_authenticated:
        if current_user.type == 'demo':
            return session.get('locale')
        return current_user.locale
    elif session.get('locale'):
        return session.get('locale')

    return request.accept_languages.best_match(['de', 'fr', 'en', 'ru'])


def get_timezone():
    if current_user.is_authenticated:
        return current_user.timezone
