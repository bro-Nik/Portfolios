from hashlib import new
import json
from flask import Response, jsonify, render_template, redirect, send_file, url_for, request, flash, session, Blueprint
from flask_babel import gettext
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import requests
import pickle

from portfolio_tracker.app import db, login_manager, redis, app
from portfolio_tracker.general_functions import float_
from portfolio_tracker.models import Alert, Asset, Portfolio, Transaction, User, WalletAsset, WalletTransaction, WhitelistTicker, userInfo, Wallet
from portfolio_tracker.wallet.wallet import get_wallet_asset
from portfolio_tracker.whitelist.whitelist import get_whitelist_ticker


login_manager.login_view = 'user.login'
login_manager.login_message = gettext('Please log in to access this page')
login_manager.login_message_category = 'danger'


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
            new_user = User(email=email,
                            password=hash_password,
                            locale=get_locale(),
                            currency='usd')
            db.session.add(new_user)

            new_user.wallets.append(Wallet(name=gettext('Default Wallet')))
            new_user.info = userInfo(first_visit=datetime.now())

            db.session.commit()

            return redirect(url_for('.login'))

    return render_template('user/register.html', locale=get_locale())


@user.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.type != 'demo':
	    return redirect(url_for('portfolio.portfolios'))
	
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

        create_first_wallet()

    db.session.commit()
    flash(gettext('Profile cleared'), 'success')

    return ''


def create_first_wallet():
    wallet = Wallet(name=gettext('Default Wallet'))
    wallet.wallet_assets.append(WalletAsset(ticker_id='cu-usd'))
    current_user.wallets.append(wallet)


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
            for body in asset.bodies:
                db.session.delete(body)
            for transaction in asset.transactions:
                db.session.delete(transaction)
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
    # For export to demo user
    if request.args.get('demo_user') and current_user.type == 'admin':
        user = db.session.execute(db.select(User).
                                  filter_by(type='demo')).scalar()
    else:
        user = current_user

    prefixes = {'crypto': 'cr-', 'stocks': 'st-', 'currency': 'cu-'}

    result = {'wallets': [],
              'portfolios': [],
              'whitelist_tickers': [],
              'prefixes': prefixes}

    for wallet in user.wallets:
        w = {'id': wallet.id,
             'name': wallet.name,
             'comment': wallet.comment,
             'assets': []}

        for asset in wallet.wallet_assets:
            a = {'ticker_id': asset.ticker_id,
                 'transactions': []}

            for transaction in asset.wallet_transactions:
                a['transactions'].append({
                    'id': transaction.id,
                    'date': transaction.date,
                    'related_transaction': transaction.related_transaction,
                    'amount': transaction.amount,
                    'type': transaction.type
                })

            w['assets'].append(a)
        result['wallets'].append(w)


    for portfolio in user.portfolios:
        p = {'market': portfolio.market,
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
                    'amount': transaction.amount,
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

    for whitelist_ticker in user.whitelist_tickers:
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
    # For import to demo user
    if request.args.get('demo_user') and current_user.type == 'admin':
        user = db.session.execute(db.select(User).
                                  filter_by(type='demo')).scalar()
        url = url_for('admin.demo_user', )
    else:
        user = current_user
        url = url_for('.settings_export_import')

    try:
        data = json.loads(request.form['import'])
    except:
        flash(gettext('Error reading data'), 'danger')
        return redirect(url)

    old_prefixes = data['prefixes']
    prefixes = {'crypto': 'cr-', 'stocks': 'st-', 'currency': 'cu-'}

    def get_new_wallet_id(old_id):
        for wallet in data['wallets']:
            if old_id == wallet['id']:
                return int(wallet['new_id'])
        return None

    def get_new_transaction_id(old_id):
        for wallet in data['wallets']:
            for asset in wallet['assets']:
                for transaction in asset['transactions']:
                    if old_id == transaction['id']:
                        return int(transaction['new_id']) 
        return None


    wallet_transactions = []
    for wallet in data['wallets']:
        new_wallet = Wallet(user_id=user.id,
                            name=wallet['name'],
                            comment=wallet['comment'])
        db.session.add(new_wallet)
        db.session.commit()
        wallet['new_id'] = new_wallet.id

        for asset in wallet['assets']:
            new_asset = WalletAsset(ticker_id=asset['ticker_id'])
            new_wallet.wallet_assets.append(new_asset)

            for transaction in asset['transactions']:
                new_transaction = WalletTransaction(
                    wallet_asset_id=new_asset.id,
                    related_transaction=transaction['related_transaction'],
                    date=transaction['date'],
                    amount=transaction['amount'],
                    type=transaction['type']
                    )
                new_asset.wallet_transactions.append(new_transaction)
                db.session.commit()
                transaction['new_id'] = new_transaction.id
                wallet_transactions.append(new_transaction)

    db.session.commit()

    for transaction in wallet_transactions:
        related = get_new_transaction_id(transaction.related_transaction)
        transaction.related_transaction = related


    for portfolio in data['portfolios']:
        new_portfolio = Portfolio(user_id=user.id,
                                  market=portfolio['market'],
                                  name=portfolio['name'],
                                  comment=portfolio['comment'])
        db.session.add(new_portfolio)

        old_prefix_len = len(old_prefixes[new_portfolio.market])
        prefix = prefixes[new_portfolio.market]

        for asset in portfolio['assets']:
            new_asset = Asset(ticker_id=prefix + asset['ticker_id'][old_prefix_len:],
                              percent=float_(asset['percent'], 0),
                              comment=asset['comment'])
            new_portfolio.assets.append(new_asset)

            for transaction in asset['transactions']:
                wallet_id = get_new_wallet_id(transaction['wallet_id'])
                wallet_asset = get_wallet_asset(ticker_id=new_asset.ticker_id,
                                                wallet_id=wallet_id,
                                                create=True)
                new_transaction = Transaction(
                    wallet_asset_id=wallet_asset.id,
                    against_ticker_id='cu-usd',
                    date=transaction['date'],
                    quantity=transaction['quantity'],
                    price=transaction['price'],
                    price_usd=transaction['price'],
                    amount=transaction['amount'],
                    type=transaction['type'],
                    comment=transaction['comment'],
                    wallet_id=wallet_id,
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
                        type='down' if new_transaction.type == '+' else 'up',
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

    flash(gettext('Import completed'), 'success')

    return redirect(url)


def get_locale():
    if current_user.is_authenticated:
        if current_user.type == 'demo':
            return session.get('locale')
        return current_user.locale if current_user.locale else session.get('locale')
    elif session.get('locale'):
        return session.get('locale')

    return request.accept_languages.best_match(['en', 'ru'])


def get_currency():
    currency = session.get('currency')
    currency = currency if currency else 'usd'
    if current_user.type == 'demo':
        return currency
    return current_user.currency if current_user.currency else currency

app.add_template_filter(get_currency)


def get_timezone():
    if current_user.is_authenticated:
        return current_user.timezone


@user.route('/ajax_locales', methods=['GET'])
@login_required
def ajax_locales():
    result = [{'value': 'en', 'text': 'EN', 'subtext': 'English'},
              {'value': 'ru', 'text': 'RU', 'subtext': 'Русский'}]

    return json.dumps(result, ensure_ascii=False)


@user.route('/change_locale', methods=['GET'])
def change_locale():
    locale = request.args.get('value')
    if current_user.is_authenticated and current_user.type != 'demo':
        current_user.locale = locale
        db.session.commit()
    else:
        session['locale'] = locale
    return ''


@user.route('/change_currency', methods=['GET'])
def change_currency():
    currency = request.args.get('value')
    if current_user.is_authenticated and current_user.type != 'demo':
        current_user.currency = currency
        db.session.commit()
    else:
        session['currency'] = currency
    return ''
