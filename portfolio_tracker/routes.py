import pickle
from flask import render_template, url_for, redirect
from sqlalchemy import func
from flask_login import login_required, current_user

from portfolio_tracker.app import app, redis, db
from portfolio_tracker.models import Alert, User, WhitelistTicker


@app.route('/')
def index():
    return render_template('index.html')


@app.errorhandler(404)
@login_required
def page_not_found(e):
    return render_template('404.html')


@app.route("/json/worked_alerts_count")
@login_required
def worked_alerts_count():
    count = db.session.execute(
        db.select(func.count()).select_from(User).
        filter(User.id == current_user.id).
    join(User.whitelist_tickers).
    join(WhitelistTicker.alerts).
    filter(Alert.status == 'worked')).scalar()

    if count:
        return '<span>' + str(count) + '</span>'
    else:
        return ''
