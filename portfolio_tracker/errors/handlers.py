from flask import render_template

from portfolio_tracker.app import db
from portfolio_tracker.errors import bp


# 404 - Page Not Found
@bp.app_errorhandler(404)
def page_not_found(error):
    return render_template('errors/404.html'), 404


# 500 - Internal Server Error
@bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500


# 400 - Bad Request
@bp.errorhandler(400)
def bad_request(e):
    return render_template('errors/400.html'), 400


# 403 - Forbidden
@bp.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


# 405 - Method Not Allowed
@bp.errorhandler(405)
def method_not_allowed(e):
    return render_template('errors/405.html'), 405
