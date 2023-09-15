from functools import wraps
from flask import session, request, redirect, url_for, abort, flash
from flask_login import current_user

from portfolio_tracker.app import db
from portfolio_tracker.models import User

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated:
            admins_in_base = db.session.execute(db.select(User).filter_by(type='admin')).scalar()
            if admins_in_base:
                if current_user.type != 'admin':
                    abort(404)
            return f(*args, **kwargs)
        else:
            return redirect(url_for('user.login') + '?next=' + request.url)
    return decorated_function

demo_can_change = True

def demo_user_change(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.type == 'demo' and not demo_can_change:
            flash('Демо пользователь не может вносить изменения', 'danger')
            return ''
        return f(*args, **kwargs)
    return decorated_function



