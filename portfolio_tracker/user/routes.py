import json

from flask import render_template, redirect, url_for, request, session, flash
from flask_login import login_user, login_required, current_user, logout_user
from flask_babel import gettext

from ..general_functions import actions_in, print_flash_messages
from ..repository import Repository
from ..settings import LANGUAGES
from ..wraps import closed_for_demo_user
from .repository import UserRepository
from .service import UserService
from . import bp, utils


us = UserService(current_user)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Отдает страницу входа и принимает форму."""

    # Если это авторизованный пользователь - перебросить
    if us.is_authenticated() and not us.is_demo():
        return redirect(url_for('portfolio.portfolios'))

    # Проверка данных входа
    if request.method == 'POST':
        result, messages = utils.login(request.form)
        print_flash_messages(messages)

        if result is True:
            page = request.args.get('next', url_for('portfolio.portfolios'))
            Repository.save()
            return redirect(page)

    return render_template('user/login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Отдает страницу регистрации и принимает форму."""

    # Если это авторизованный пользователь - перебросить
    if us.is_authenticated() and not us.is_demo():
        return redirect(url_for('portfolio.portfolios'))

    # Проверка данных входа
    if request.method == 'POST':
        result, messages = utils.register(request.form)
        print_flash_messages(messages)

        if result is True:
            return redirect(url_for('.login'))

    return render_template('user/register.html', locale=utils.get_locale())


@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['GET', 'POST'])
def change_password():
    """Отдает страницу смены пароля и принимает форму."""

    # Проверка данных входа
    if request.method == 'POST':
        result, messages = utils.change_password(request.form)
        print_flash_messages(messages)

        if result is True:
            Repository.save()

    return render_template('user/password.html', locale=utils.get_locale())


@bp.route('/logout')
@login_required
@closed_for_demo_user(['GET', 'POST'])
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
@closed_for_demo_user(['GET', 'POST'])
def user_action():
    """Действия над пользователем."""
    actions_in(request.data, UserRepository.get)
    Repository.save()

    if not us.is_authenticated():
        return {'redirect': str(url_for('user.login'))}
    return ''


@bp.route('/demo_user')
def demo_user():
    demo = UserRepository.get_demo_user()
    login_user(demo)
    return redirect(url_for('portfolio.portfolios'))


@bp.route('/settings_profile')
@login_required
@closed_for_demo_user(['GET', 'POST'])
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
    if us.is_authenticated() and not us.is_demo():
        us.change_locale(locale)
        Repository.save()
    else:
        session['locale'] = locale
    return ''


@bp.route('/change_currency', methods=['GET'])
def change_currency():
    currency = request.args.get('value')
    if us.is_authenticated() and not us.is_demo():
        us.change_currency(currency)
        Repository.save()
    else:
        session['currency'] = currency or 'usd'
    return ''
