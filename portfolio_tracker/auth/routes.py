from flask import render_template, redirect, url_for, request, flash
from flask_babel import gettext
from flask_login import login_user, login_required, logout_user, current_user

from portfolio_tracker.auth import bp
from portfolio_tracker.auth.utils import create_new_user, find_user
from portfolio_tracker.user.utils import get_locale


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
        email = request.form.get('email')
        password = request.form.get('password')
        password2 = request.form.get('password2')

        if not (email and password and password2):
            flash(gettext('Заполните адрес электронной почты, '
                          'пароль и подтверждение пароля'), 'danger')

        elif find_user(email):
            flash(gettext('Данный почтовый ящик уже используется'), 'danger')

        elif password != password2:
            flash(gettext('Пароли не совпадают'), 'danger')

        else:
            create_new_user(email, password)
            flash(gettext('Вы зарегистрированы. Теперь войдите в систему'),
                  'success')

            return redirect(url_for('.login'))

    return render_template('auth/register.html', locale=get_locale())


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Отдает страницу входа и принимает форму входа."""
    if current_user.is_authenticated and current_user.type != 'demo':
        return redirect(url_for('portfolio.portfolios'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash(gettext('Введити адрес электронной почты и пароль'),
                  'danger')

        else:
            user = find_user(email)
            if user and user.check_password(password):
                login_user(user,
                           request.form.get('remember-me', False, type=bool))
                user.new_login()

                next_page = request.args.get('next')
                if not next_page:
                    next_page = url_for('portfolio.portfolios')
                return redirect(next_page)

            flash(gettext('Неверный адрес электронной почты или пароль'),
                  'danger')

    return render_template('auth/login.html', locale=get_locale())
