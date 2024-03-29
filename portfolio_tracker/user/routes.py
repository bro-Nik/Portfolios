import json

from flask import render_template, redirect, url_for, request, flash, session
from flask_babel import gettext
from flask_login import login_user, login_required, current_user, logout_user

from ..app import db
from ..settings import LANGUAGES
from ..wraps import demo_user_change
from ..wallet.utils import create_wallet
from . import bp, utils


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Отдает страницу входа и принимает форму."""
    if current_user.is_authenticated and current_user.type != 'demo':
        return redirect(url_for('portfolio.portfolios'))

    if request.method == 'POST':
        # Проверка данных
        if utils.login(request.form) is True:
            db.session.commit()
            page = request.args.get('next', url_for('portfolio.portfolios'))
            return redirect(page)

    return render_template('user/login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Отдает страницу регистрации и принимает форму."""
    if current_user.is_authenticated and current_user.type != 'demo':
        return redirect(url_for('portfolio.portfolios'))

    if request.method == 'POST':
        # Регистрация
        if utils.register(request.form) is True:
            db.session.commit()
            return redirect(url_for('.login'))

    return render_template('user/register.html', locale=utils.get_locale())


@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
@demo_user_change
def change_password():

    if request.method == 'POST':
        # Проверка старого пароля
        if current_user.check_password(request.form.get('old_pass')):
            new_pass = request.form.get('new_pass')
            # Пароль с подтверждением совпадают
            if new_pass == request.form.get('new_pass2'):
                current_user.set_password(new_pass)
                db.session.commit()
                flash(gettext('Пароль обновлен'), 'success')
            else:
                flash(gettext('Новые пароли не совпадают'), 'danger')
        else:
            flash(gettext('Не верный старый пароль'), 'danger')

    return render_template('user/password.html', locale=utils.get_locale())


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
        return redirect(f"{url_for('.login')}?next={request.url}")

    return response


@bp.route('/user_action', methods=['POST'])
@login_required
def user_action():
    data = json.loads(request.data) if request.data else {}
    action = data.get('action')

    if action == 'delete':
        current_user.delete()
        db.session.commit()
        return {'redirect': str(url_for('user.login'))}

    if action == 'delete_data':
        current_user.cleare()
        create_wallet(user=current_user, first=True)
        db.session.commit()
        flash(gettext('Профиль очищен'), 'success')

    return ''


@bp.route('/demo_user')
def demo_user():
    login_user(utils.get_demo_user())
    return redirect(url_for('portfolio.portfolios'))


@bp.route('/settings_profile')
@login_required
def settings_profile():
    return render_template('user/settings_profile.html')


@bp.route('/ajax_locales', methods=['GET'])
def ajax_locales():
    result = []
    for loc, lang in LANGUAGES.items():
        result.append({'value': loc, 'text': loc.upper(), 'subtext': lang})

    return json.dumps(result, ensure_ascii=False)


@bp.route('/change_locale', methods=['GET'])
def change_locale():
    locale = request.args.get('value')
    if current_user.is_authenticated and current_user.type != 'demo':
        current_user.change_locale(locale)
        db.session.commit()
    else:
        session['locale'] = locale
    return ''


@bp.route('/change_currency', methods=['GET'])
def change_currency():
    currency = request.args.get('value')
    if current_user.is_authenticated and current_user.type != 'demo':
        current_user.change_currency(currency)
        db.session.commit()
    else:
        session['currency'] = currency or 'usd'
    return ''
