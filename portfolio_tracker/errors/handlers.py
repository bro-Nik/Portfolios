from flask import current_app, render_template, request

from ..app import db
from . import bp


@bp.app_errorhandler(404)
def page_not_found(_):
    """404 - Page Not Found."""
    current_app.logger.warning(f'{_} # {request.url}')
    return render_template('errors/404.html'), 404


@bp.app_errorhandler(500)
def internal_error(_):
    """500 - Internal Server Error."""
    db.session.rollback()
    current_app.logger.warning(f'{_} # {request.url}')
    return render_template('errors/500.html'), 500


@bp.errorhandler(400)
def bad_request(_):
    """400 - Bad Request."""
    current_app.logger.warning(f'{_} # {request.url}')
    return render_template('errors/400.html'), 400


@bp.errorhandler(403)
def forbidden(_):
    """403 - Forbidden."""
    current_app.logger.warning(f'{_} # {request.url}')
    return render_template('errors/403.html'), 403


@bp.errorhandler(405)
def method_not_allowed(_):
    """405 - Method Not Allowed."""
    current_app.logger.warning(f'{_} # {request.url}')
    return render_template('errors/405.html'), 405
