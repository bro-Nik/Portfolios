from flask import render_template

from portfolio_tracker.app import db
from portfolio_tracker.errors import bp


@bp.app_errorhandler(404)
def page_not_found(error):
    return render_template('errors/404.html'), 404


@bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500
