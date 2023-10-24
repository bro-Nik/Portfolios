from datetime import datetime
from flask import render_template
from sqlalchemy import func
from flask_login import login_required, current_user

from portfolio_tracker.app import app, db
from portfolio_tracker.models import Alert, Ticker, User, WatchlistAsset
from portfolio_tracker.user.user import get_locale


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', locale=get_locale())




@app.errorhandler(404)
@login_required
def page_not_found(error):
    return render_template('404.html'), 404


@app.route('/json/worked_alerts_count', methods=['GET'])
@login_required
def worked_alerts_count():
    count = db.session.execute(
        db.select(func.count()).select_from(User).
        filter(User.id == current_user.id).
    join(User.whitelist_tickers).
    join(WatchlistAsset.alerts).
    filter(Alert.status == 'worked')).scalar()

    if count:
        return '<span>' + str(count) + '</span>'
    else:
        return ''


@app.before_request
def before_request():
    if current_user.is_authenticated:
        if current_user.info:
            current_user.info.last_visit = datetime.utcnow()
            db.session.commit()
