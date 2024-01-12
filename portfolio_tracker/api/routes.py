from flask_login import login_required

from . import bp, utils


@bp.before_request
def before_request():
    utils.update_user_last_visit()


@bp.route('/worked_alerts_count', methods=['GET'])
@login_required
def worked_alerts_count():
    count = utils.get_worked_alerts_count()
    return '<span>' + str(count) + '</span>' if count else ''
