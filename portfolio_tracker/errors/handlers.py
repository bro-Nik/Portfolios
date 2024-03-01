from flask import current_app, render_template, request

from ..admin.integrations_other import OtherIntegration
from ..app import db
from . import bp


def new_error(error_code: int):
    request_checker = OtherIntegration('requests')

    # Получение IP
    ip = request.headers.get('X-Real-IP')

    # Логи
    m = f'{error_code} # {ip if ip else "IP не определен"} # {request.url}'
    current_app.logger.warning(m)
    request_checker.logs.set('warning', m)


@bp.app_errorhandler(404)
def page_not_found(_):
    """404 - Page Not Found."""
    new_error(404)
    return render_template('errors/404.html'), 404


@bp.app_errorhandler(500)
def internal_error(_):
    """500 - Internal Server Error."""
    db.session.rollback()
    new_error(500)
    return render_template('errors/500.html'), 500


@bp.errorhandler(400)
def bad_request(_):
    """400 - Bad Request."""
    new_error(400)
    return render_template('errors/400.html'), 400


@bp.errorhandler(403)
def forbidden(_):
    """403 - Forbidden."""
    new_error(403)
    return render_template('errors/403.html'), 403


@bp.errorhandler(405)
def method_not_allowed(_):
    """405 - Method Not Allowed."""
    new_error(405)
    return render_template('errors/405.html'), 405
