from flask import Flask, request, render_template, redirect, url_for, request
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

from portfolio_tracker.models import Setting, Market
from portfolio_tracker.defs import *


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run()


@app.route('/first_start', methods=['GET', 'POST'])
def first_start():
    ''' Страница первого запуска '''
    if request.method == 'GET':
        print(cg.get_coins_markets('usd', per_page='200', page=1))
        return render_template('first_start.html')

    if request.method == 'POST':

        global settings_list
        # маркеты
        if request.form.get('crypto'):
            crypto = Market(name='Crypto',
                            id='crypto')
            db.session.add(crypto)

            # период обновления
            crypto_update_price = Setting(name='crypto',
                                          value=5)
            db.session.add(crypto_update_price)
        if request.form.get('stocks'):
            stocks = Market(name='Stocks',
                            id='stocks')
            db.session.add(stocks)
            # период обновления
            stocks_update_price = Setting(name='stocks',
                                          value=0)
            db.session.add(stocks_update_price)
            # API
            api_key_polygon = Setting(
                name='api_key_polygon',
                value=request.form.get('api_key_polygon')
            )
            settings_list['api_key_polygon'] = request.form.get('api_key_polygon')
            db.session.add(api_key_polygon)

        # загрузка тикеров
        if request.form.get('crypto'):
            tickers_load('crypto')
        if request.form.get('stocks'):
            tickers_load('stocks')

        return "<h1>Ready!</h1><p>Restart app</p>"
