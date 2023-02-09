from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy

#  flask --app portfolio_tracker/first_start run
# go to /first_start
def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('settings.py')

    db = SQLAlchemy()
    db.init_app(app)
    return app, db

app, db = create_app()

from portfolio_tracker.models import Market, User
from portfolio_tracker.defs import *

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run()


@app.route('/first_start', methods=['GET', 'POST'])
def first_start():
    ''' Страница первого запуска '''
    if request.method == 'GET':
        return render_template('first_start.html')

    if request.method == 'POST':
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

        # загрузка тикеров
        load_crypto_tickers(99 if request.form.get('test') else 1000, 'crypto')
        load_stocks_tickers(99 if request.form.get('test') else 1000, 'stocks')

        return "<h1>Ready!</h1><p>Restart app</p>"
