import json

from flask import render_template, redirect, url_for, request, flash, session
from flask_babel import gettext
from flask_login import login_user, login_required, current_user, logout_user

from ..app import db
from ..settings import LANGUAGES
from ..wraps import demo_user_change
from ..wallet.utils import create_new_wallet
from . import bp, utils


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

    return render_template('user/login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Отдает страницу регистрации и принимает форму регистрации."""
    if current_user.is_authenticated and current_user.type != 'demo':
        return redirect(url_for('portfolio.portfolios'))

    if request.method == 'POST':
        if utils.register(request.form):
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

    if action == 'delete_user':
        current_user.delete()
        return {'redirect': str(url_for('user.login'))}

    if action == 'delete_data':
        current_user.cleare()
        create_new_wallet(current_user)
        flash(gettext('Профиль очищен'), 'success')

    db.session.commit()
    return ''


@bp.route('/demo_user')
def demo_user():
    login_user(utils.get_demo_user())
    return redirect(url_for('portfolio.portfolios'))


@bp.route('/settings_profile')
@login_required
def settings_profile():
    return render_template('user/settings_profile.html')


# @bp.route('/settings_export_import', methods=['GET'])
# @login_required
# def settings_export_import():
#     return render_template('user/settings_export_import.html')
#
#
# @bp.route('/export', methods=['GET'])
# @login_required
# def export_data():
#     # For export to demo user
#     if request.args.get('demo_user') and current_user.type == 'admin':
#         user = utils.get_demo_user()
#     else:
#         user = current_user
#     if not user:
#         return ''
#
#     filename = f'portfolios_export ({datetime.now().date()}).txt'
#
#     return Response(
#         json.dumps(user.export_data()),
#         mimetype='application/json',
#         headers={'Content-disposition': f'attachment; filename={filename}'})
#
#
# @bp.route('/import_post', methods=['POST'])
# @login_required
# def import_data_post():
#     # For import to demo user
#     if request.args.get('demo_user') and current_user.type == 'admin':
#         user = utils.get_demo_user()
#         url = url_for('admin.demo_user', )
#     else:
#         user = current_user
#         url = url_for('.settings_export_import')
#
#     if not user:
#         return ''
#
#     file = request.files['file']
#     if file:
#         data = file.read()
#
#         try:
#             data = json.loads(data)
#             user.import_data(data)
#             flash(gettext('Импорт заверщен'), 'success')
#         except (json.decoder.JSONDecodeError, ValueError):
#             flash(gettext('Ошибка чтения данных'), 'danger')
#         except Exception as e:
#             flash(gettext('Неизвестная ошибка'), 'danger')
#             print(e)
#
#     return redirect(url)
#

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
