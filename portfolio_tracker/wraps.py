from functools import wraps
import time

from flask import current_app, request, redirect, url_for, abort, flash
from flask_babel import gettext
from flask_login import current_user


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated:
            if current_user.type != 'admin':
                abort(404)
            return f(*args, **kwargs)

        return redirect(url_for('user.login') + '?next=' + request.url)
    return decorated_function


def demo_user_change(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.type == 'demo':
            flash(gettext('Демо юзер не может вносить изменения'), 'warning')
            return ''
        return f(*args, **kwargs)
    return decorated_function


def logging(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start = time.perf_counter()
        n = f.__name__
        current_app.logger.info(f'{n}: Старт')

        res = f(*args, **kwargs)

        t = time.perf_counter() - start
        current_app.logger.info(f'{n}: Конец ## Время выполнения: {t} сек')
        return res

    return decorated_function
