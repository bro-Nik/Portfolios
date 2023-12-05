from flask import render_template, redirect, url_for, request
from flask_login import login_required, logout_user, current_user

from portfolio_tracker.user.utils import get_locale
from . import bp, utils


@bp.route('/logout')
@login_required
def logout():
    """Выводит пользователя из системы."""
    logout_user()
    return redirect(url_for('.login'))


@bp.after_request
def redirect_to_signin(response):
    """Перекидывает на странизу авторизации."""
    if response.status_code == 401:
        return redirect(f"{url_for('auth.login')}?next={request.url}")

    return response


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Отдает страницу регистрации и принимает форму регистрации."""
    if request.method == 'POST':
        if utils.register(request.form) is True:
            return redirect(url_for('.login'))

    return render_template('auth/register.html', locale=get_locale())


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Отдает страницу входа и принимает форму входа."""
    if current_user.is_authenticated and current_user.type != 'demo':
        return redirect(url_for('portfolio.portfolios'))

    if request.method == 'POST':
        if utils.login(request.form) is True:
            next_page = request.args.get('next',
                                         url_for('portfolio.portfolios'))
            return redirect(next_page)

    return render_template('auth/login.html', locale=get_locale())
