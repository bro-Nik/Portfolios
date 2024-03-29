from functools import wraps

from flask import request, redirect, url_for, abort, flash
from flask_babel import gettext
from flask_login import current_user


def admin_only(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated:
            if current_user.type != 'admin':
                abort(404)
            return func(*args, **kwargs)

        return redirect(url_for('user.login') + '?next=' + request.url)
    return decorated_function


def demo_user_change(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.type == 'demo':
            flash(gettext('Демо юзер не может вносить изменения'), 'warning')
            return ''
        return func(*args, **kwargs)
    return decorated_function
