import json

from flask import render_template, redirect, url_for, request, session
from flask_login import login_user, login_required, current_user, logout_user
from flask_babel import gettext

from ..general_functions import actions_on_objects, print_flash_messages
from ..settings import LANGUAGES
from ..wraps import closed_for_demo_user
from .repository import UserRepository
from .services import auth, ui
from . import bp


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Отдает страницу входа и обрабатывает форму входа."""

    # Если это авторизованный пользователь - перебросить
    if current_user.is_authenticated and not current_user.is_demo:
        return redirect(url_for('portfolio.portfolios'))

    # Проверка данных
    if request.method == 'POST':
        result, messages = auth.login(request.form)
        print_flash_messages(messages)

        if result is True:
            page = request.args.get('next', url_for('portfolio.portfolios'))
            return redirect(page)

    return render_template('user/login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Отдает страницу регистрации и обрабатывает форму регистрации."""

    # Если это авторизованный пользователь - перебросить
    if current_user.is_authenticated and not current_user.is_demo:
        return redirect(url_for('portfolio.portfolios'))

    # Проверка данных
    if request.method == 'POST':
        result, messages = auth.register(request.form)
        print_flash_messages(messages)

        if result is True:
            return redirect(url_for('.login'))

    return render_template('user/register.html', locale=ui.get_locale())


@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['GET', 'POST'])
def change_password():
    """Отдает страницу смены пароля и принимает форму смены пароля."""

    # Проверка данных
    if request.method == 'POST':
        result, messages = auth.change_password(request.form)
        print_flash_messages(messages)

        if result is True:
            UserRepository.save(current_user)

    return render_template('user/password.html', locale=ui.get_locale())


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
    actions_on_objects(request.data, UserRepository.get)
    print_flash_messages([gettext('Готово'), 'success'])

    if not current_user.is_authenticated:
        return {'redirect': str(url_for('user.login'))}
    return ''


@bp.route('/demo_user')
def demo_user():
    """Вход в демо."""
    demo = UserRepository.get_demo_user()
    login_user(demo)
    return redirect(url_for('portfolio.portfolios'))


@bp.route('/settings_profile')
@login_required
@closed_for_demo_user(['GET', 'POST'])
def settings_profile():
    """Страница настроек пользователя."""
    return render_template('user/settings_profile.html')


@bp.route('/ajax_locales', methods=['GET'])
def ajax_locales():
    """Список доступных локализаций."""
    result = []
    for loc, lang in LANGUAGES.items():
        result.append({'value': loc, 'text': loc.upper(), 'subtext': lang})

    return json.dumps(result, ensure_ascii=False)


@bp.route('/change_locale', methods=['GET'])
def change_locale():
    """Смена локализации пользователя или демо пользователя."""
    locale = request.args.get('value')
    if current_user.is_authenticated and not current_user.is_demo:
        current_user.service.change_locale(locale)
        UserRepository.save(current_user)
    else:
        session['locale'] = locale
    return ''


@bp.route('/change_currency', methods=['GET'])
def change_currency():
    """Смена валюты пользователя или демо пользователя."""
    currency = request.args.get('value')
    if current_user.is_authenticated and not current_user.is_demo:
        current_user.service.change_currency(currency)
        UserRepository.save(current_user)
    else:
        session['currency'] = currency or 'usd'
    return ''
