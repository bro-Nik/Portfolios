from datetime import datetime
from flask import current_app, render_template, request

from ..admin.utils import get_module
from ..app import db
from . import bp


def log(error, url):
    current_app.logger.warning(f'{error} # {url}')
    module = get_module('requests')
    if module:
        module.logs.set('warning', f'{error} # {url} # {datetime.now()}')


@bp.app_errorhandler(404)
def page_not_found(error):
    """404 - Page Not Found."""
    log(error, request.url)
    return render_template('errors/404.html'), 404


@bp.app_errorhandler(500)
def internal_error(error):
    """500 - Internal Server Error."""
    db.session.rollback()
    log(error, request.url)
    return render_template('errors/500.html'), 500


@bp.errorhandler(400)
def bad_request(error):
    """400 - Bad Request."""
    log(error, request.url)
    return render_template('errors/400.html'), 400


@bp.errorhandler(403)
def forbidden(error):
    """403 - Forbidden."""
    log(error, request.url)
    return render_template('errors/403.html'), 403


@bp.errorhandler(405)
def method_not_allowed(error):
    """405 - Method Not Allowed."""
    log(error, request.url)
    return render_template('errors/405.html'), 405
