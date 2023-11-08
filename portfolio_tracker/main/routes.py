from flask_babel import gettext
from sqlalchemy import func
from flask_login import login_required, current_user

from portfolio_tracker.app import db
from portfolio_tracker.main import bp
from portfolio_tracker.user.utils import get_locale


@bp.route('/json/worked_alerts_count', methods=['GET'])
@login_required
def worked_alerts_count():
    count = db.session.execute(
        db.select(func.count()).select_from(User).
        filter(User.id == current_user.id).join(User.whitelist_tickers).
        join(WatchlistAsset.alerts).filter(Alert.status == 'worked')).scalar()

    if count:
        return '<span>' + str(count) + '</span>'
    else:
        return ''


# @current_app.before_request
# def before_request():
#     if current_user.is_authenticated and current_user.info:
        # current_user.info.last_visit = datetime.utcnow()
        # db.session.commit()


