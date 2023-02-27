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
            return redirect(url_for('login') + '?next=' + request.url)
    return decorated_function

demo_not_can_change = True

def demo_user_change(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.email == 'demo':
            if demo_not_can_change:
                flash('Демо пользователь не может вносить изменения')
                return redirect(session['last_url'])
    return decorated_function



