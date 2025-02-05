from functools import wraps
from typing import List

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


def closed_for_demo_user(methods: List):
    def actual_decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            if current_user.type == 'demo' and request.method in methods and False:
                if request.method == 'POST':
                    flash(gettext('Демо юзер не может вносить изменения'), 'warning')
                    return ''
                abort(403)
            return func(*args, **kwargs)
        return decorated_function
    return actual_decorator
