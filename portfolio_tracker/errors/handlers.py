from flask import render_template, request

from ..admin.int_request_checker import request_checker
from ..app import db
from . import bp


@bp.app_errorhandler(404)
def page_not_found(error):
    """404 - Page Not Found."""
    request_checker.new_error(404)
    return render_template('errors/404.html'), 404


@bp.app_errorhandler(500)
def internal_error(error):
    """500 - Internal Server Error."""
    db.session.rollback()
    request_checker.new_error(500)
    return render_template('errors/500.html'), 500


@bp.errorhandler(400)
def bad_request(error):
    """400 - Bad Request."""
    request_checker.new_error(400)
    return render_template('errors/400.html'), 400


@bp.errorhandler(403)
def forbidden(error):
    """403 - Forbidden."""
    request_checker.new_error(403)
    return render_template('errors/403.html'), 403


@bp.errorhandler(405)
def method_not_allowed(error):
    """405 - Method Not Allowed."""
    request_checker.new_error(405)
    return render_template('errors/405.html'), 405
