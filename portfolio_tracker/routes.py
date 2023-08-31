import pickle
from flask import render_template, url_for, redirect
from sqlalchemy import func
from flask_login import login_required, current_user

from portfolio_tracker.app import app, redis, db
from portfolio_tracker.models import Alert, User, WhitelistTicker


@app.route('/')
@login_required
def index():
    return redirect(url_for('portfolio.portfolios'))


@app.route('/settings')
@login_required
def settings():
    """ Settings page """
    return render_template('settings.html')


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


@app.route("/1")
@login_required
def w1():
    tracked_tickers = db.session.execute(
        db.select(WhitelistTicker).filter(WhitelistTicker.alerts)).scalars()

    for ticker in tracked_tickers:
        for alert in ticker.alerts:
            alert.status = 'worked'

    db.session.commit()

    return ''
