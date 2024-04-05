from flask import current_app, render_template, request

from ..admin.integrations_other import OtherIntegration
from ..app import db


def init_request_errors(app):
    app.register_error_handler(400, bad_request)
    app.register_error_handler(403, forbidden)
    app.register_error_handler(404, page_not_found)
    app.register_error_handler(405, method_not_allowed)
    app.register_error_handler(500, internal_error)


def new_error(error_code: int):
    request_checker = OtherIntegration('requests')

    # Получение IP
    ip = request.headers.get('X-Real-IP')

    # Логи
    m = f'{error_code} # {ip if ip else "IP не определен"} # {request.url}'
    current_app.logger.warning(m)
    request_checker.logs.set('warning', m)


def bad_request(_):
    """400 - Bad Request."""
    new_error(400)
    return render_template('errors/400.html'), 400


def forbidden(_):
    """403 - Forbidden."""
    new_error(403)
    return render_template('errors/403.html'), 403


def page_not_found(_):
    """404 - Page Not Found."""
    new_error(404)
    return render_template('errors/404.html'), 404


def method_not_allowed(_):
    """405 - Method Not Allowed."""
    new_error(405)
    return render_template('errors/405.html'), 405


def internal_error(_):
    """500 - Internal Server Error."""
    db.session.rollback()
    new_error(500)
    return render_template('errors/500.html'), 500
