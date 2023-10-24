import json
from flask import Response, jsonify, render_template, redirect, send_file, url_for, request, flash, session, Blueprint
from flask_babel import gettext
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.urls import url_parse
from datetime import datetime
import requests

from portfolio_tracker.app import db, login_manager, redis, app
from portfolio_tracker.general_functions import float_
from portfolio_tracker.models import Alert, Asset, Portfolio, Ticker, Transaction, User, WalletAsset, WatchlistAsset, userInfo, Wallet
from portfolio_tracker.watchlist.watchlist import get_watchlist_asset


login_manager.login_view = 'user.login'
login_manager.login_message = gettext('Пожалуйста, войдите, чтобы получить доступ к этой странице')
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
            flash(gettext('Заполните адрес электронной почты, пароль и подтверждение пароля'), 'danger')
        elif get_user(email):
            flash(gettext('Данный почтовый ящик уже используется'), 'danger')
        elif password != password2:
            flash(gettext('Пароли не совпадают'), 'danger')
        else:
            hash_password = generate_password_hash(password)
            new_user = User(email=email,
                            password=hash_password,
                            locale=get_locale(),
                            currency='usd')
            db.session.add(new_user)

            new_user.info = userInfo(first_visit=datetime.now())
            create_first_wallet(new_user)

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
            flash(gettext('Введити адрес электронной почты и пароль'), 'danger')

        user = get_user(email)
        if user and check_password_hash(user.password, password):
            login_user(user, remember=request.form.get('remember-me')) 
            new_visit()
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = redirect(url_for('portfolio.portfolios'))
            return redirect(next_page)
        else:
            flash(gettext('Неверный адрес электронной почты или пароль'), 'danger')

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
        user_delete_def(current_user.id, 'delete_user')
        return {'redirect': str(url_for('.login'))}

    elif action == 'delete_data':
        user_delete_def(current_user.id)
        create_first_wallet(current_user)
        flash(gettext('Профиль очищен'), 'success')

    elif action == 'update_assets':
        for wallet in current_user.wallets:
            for asset in wallet.wallet_assets:
                asset.quantity = 0
                asset.buy_orders = 0
                asset.sell_orders = 0
                for transaction in asset.transactions:
                    if transaction.type not in ('Buy', 'Sell'):
                        transaction.update_dependencies()
        for portfolio in current_user.portfolios:
            for asset in portfolio.assets:
                asset.quantity = 0
                asset.in_orders = 0
                asset.amount = 0
                for transaction in asset.transactions:
                    transaction.update_dependencies()

        db.session.commit()
        flash(gettext('Активы пересчитаны'), 'success')

        

    db.session.commit()

    return ''


def create_first_wallet(user):
    wallet = Wallet(name=gettext('Кошелек по умолчанию'))
    asset = WalletAsset(ticker_id=app.config['CURRENCY_PREFIX'] + 'usd')
    wallet.wallet_assets.append(asset)
    user.wallets.append(wallet)


def user_delete_def(user_id, action=''):
    user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar()

    # alerts
    for asset in user.watchlist:
        for alert in asset.alerts:
            db.session.delete(alert)
        db.session.delete(asset)

    # wallets
    for wallet in user.wallets:
        for asset in wallet.wallet_assets:
            db.session.delete(asset)
        db.session.delete(wallet)

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

    if action == 'delete_user':
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
    from portfolio_tracker.wallet.wallet import get_wallet, get_wallet_asset

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
        flash(gettext('Ошибка чтения данных'), 'danger')
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
            new_asset = get_wallet_asset(new_wallet, asset['ticker_id'], True)

            for transaction in asset['transactions']:
                new_transaction = Transaction(
                    date=transaction['date'],
                    ticker_id=new_asset.ticker_id,
                    quantity=transaction['amount'],
                    wallet_id=new_wallet.id,
                    related_transaction_id=transaction['related_transaction']
                    )
                if new_transaction.related_transaction_id:
                    new_transaction.type = 'TransferIn' if transaction['type'] == '+1' else 'TransferOut'
                else:
                    new_transaction.type = 'Input' if transaction['type'] == '+1' else 'Output'

                new_wallet.transactions.append(new_transaction)
                db.session.commit()
                transaction['new_id'] = new_transaction.id
                wallet_transactions.append(new_transaction)

    db.session.commit()

    for transaction in wallet_transactions:
        related = get_new_transaction_id(transaction.related_transaction_id)
        transaction.related_transaction_id = related


    for portfolio in data['portfolios']:
        new_portfolio = Portfolio(user_id=user.id,
                                  market=portfolio['market'],
                                  name=portfolio['name'],
                                  comment=portfolio['comment'])
        db.session.add(new_portfolio)
        db.session.commit()

        old_prefix_len = len(old_prefixes[new_portfolio.market])
        prefix = prefixes[new_portfolio.market]

        for asset in portfolio['assets']:
            new_asset = Asset(ticker_id=prefix + asset['ticker_id'][old_prefix_len:],
                              percent=float_(asset['percent'], 0),
                              comment=asset['comment'])
            new_portfolio.assets.append(new_asset)
            db.session.commit()

            for transaction in asset['transactions']:
                wallet_id = get_new_wallet_id(transaction['wallet_id'])
                wallet = get_wallet(wallet_id)
                wallet_asset = get_wallet_asset(wallet, new_asset.ticker_id,
                                                create=True)
                new_transaction = Transaction(
                    date=transaction['date'],
                    ticker_id=new_asset.ticker_id,
                    ticker2_id='cu-usd',
                    quantity=transaction['quantity'],
                    quantity2=transaction['amount'],
                    price=transaction['price'],
                    price_usd=transaction['price'],
                    comment=transaction['comment'],
                    wallet_id=wallet_id,
                    portfolio_id=new_portfolio.id,
                    order=transaction['order']
                    )
                new_transaction.type = 'Buy' if transaction['type'] == '+1' else 'Sell'

                new_asset.transactions.append(new_transaction)

                if new_transaction.order:
                    watchlist_asset = get_watchlist_asset(new_asset.ticker_id, True)
                    new_transaction.alert.append(Alert(
                        asset_id=new_asset.id,
                        date=new_transaction.date,
                        watchlist_asset_id=watchlist_asset.id,
                        price=new_transaction.price,
                        price_usd=new_transaction.price,
                        price_ticker_id='cu-usd',
                        type='down' if new_transaction.type == '+' else 'up',
                        status='on'
                    ))

            for alert in asset['alerts']:
                watchlist_asset = get_watchlist_asset(new_asset.ticker_id, True)
                new_alert = Alert(
                    date=alert['date'],
                    asset_id=new_asset.id,
                    watchlist_asset_id=watchlist_asset.id,
                    price=alert['price'],
                    price_usd=alert['price'],
                    price_ticker_id='cu-usd',
                    type=alert['type'],
                    comment=alert['comment'],
                    status=alert['status']
                    )
                db.session.add(new_alert)

    db.session.commit()


    # for ticker in data['whitelist_tickers']:
    #     watchlist_asset = get_watchlist_asset(ticker.get('ticker_id'), True)
    #     watchlist_asset.comment = ticker.get('comment', '')
    #     
    #     for alert in ticker.get('alerts'):
    #         new_alert = Alert(
    #             date=alert.get('date'),
    #             watchlist_asset_id=watchlist_asset.id,
    #             price=alert.get('price'),
    #             price_usd=alert.get('price'),
    #             price_ticker_id='cu-usd',
    #             type=alert.get('type'),
    #             comment=alert.get('comment'),
    #             status=alert.get('status')
    #             )
    #         watchlist_asset.alerts.append(new_alert)
    #         
    # db.session.commit()


    # for portfolio in user.portfolios:
    #     for transaction in portfolio.transactions:
    #         transaction.update_dependencies()
    for wallet in user.wallets:
        for transaction in wallet.transactions:
            transaction.update_dependencies()
    db.session.commit()


    flash(gettext('Импорт заверщен'), 'success')

    return redirect(url)


def get_locale():
    if current_user.is_authenticated and current_user.type != 'demo':
        return current_user.locale or session.get('locale')
    # if current_user.is_authenticated:
    #     if current_user.type == 'demo':
    #         return session.get('locale')
    #     return current_user.locale or session.get('locale')
    # elif session.get('locale'):
    #     return session.get('locale')

    return session.get('locale') or request.accept_languages.best_match(['en', 'ru'])


def get_currency():
    if current_user.is_authenticated and current_user.type != 'demo':
        return current_user.currency
    return session.get('currency', 'usd')

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
    currency = request.args.get('value', 'usd')
    if current_user.is_authenticated and current_user.type != 'demo':
        current_user.currency = currency
        prefix = app.config['CURRENCY_PREFIX']
        current_user.currency_ticker_id = prefix + currency
        db.session.commit()
    else:
        session['currency'] = currency
    return ''
