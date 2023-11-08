import json
from json.decoder import JSONDecodeError
from flask import Response, g, render_template, redirect, url_for, request, \
    flash, session
from flask_babel import gettext
from flask_login import login_user, login_required, current_user
from datetime import datetime

from portfolio_tracker.app import db
from portfolio_tracker.settings import LANGUAGES
from portfolio_tracker.user import bp
from portfolio_tracker.user.utils import get_locale, get_demo_user


@bp.route('/user_action', methods=['POST'])
@login_required
def user_action():
    data = json.loads(request.data) if request.data else {}
    action = data.get('action')

    if action == 'delete_user':
        current_user.delete()
        return {'redirect': str(url_for('auth.login'))}

    elif action == 'delete_data':
        current_user.cleare()
        current_user.create_first_wallet()
        flash(gettext('Профиль очищен'), 'success')

    elif action == 'update_assets':
        current_user.update_assets()
        flash(gettext('Активы пересчитаны'), 'success')

    db.session.commit()
    return ''


@bp.route("/demo_user")
def demo_user():
    login_user(get_demo_user())
    return redirect(url_for('portfolio.portfolios'))


@bp.route('/settings_profile')
@login_required
def settings_profile():
    return render_template('user/settings_profile.html', locale=get_locale())


@bp.route('/settings_export_import', methods=['GET'])
@login_required
def settings_export_import():
    return render_template('user/settings_export_import.html')


@bp.route('/export', methods=['GET'])
@login_required
def export_data():
    # For export to demo user
    if request.args.get('demo_user') and current_user.type == 'admin':
        user = get_demo_user()
    else:
        user = current_user

    filename = f'portfolios_export ({datetime.now().date()}).txt'

    return Response(json.dumps(user.export_data()),
                    mimetype='application/json',
                    headers={'Content-disposition':
                             f'attachment; filename={filename}'})


@bp.route('/import_post', methods=['POST'])
@login_required
def import_data_post():
    # For import to demo user
    if request.args.get('demo_user') and current_user.type == 'admin':
        user = get_demo_user()
        url = url_for('admin.demo_user', )
    else:
        user = current_user
        url = url_for('.settings_export_import')

    file = request.files['file']
    if file:
        data = file.read()

        try:
            data = json.loads(data)
            user.import_data(data)
            flash(gettext('Импорт заверщен'), 'success')
        except (JSONDecodeError, ValueError):
            flash(gettext('Ошибка чтения данных'), 'danger')
        except Exception:
            flash(gettext('Неизвестная ошибка'), 'danger')

    return redirect(url)


@bp.route('/ajax_locales', methods=['GET'])
@login_required
def ajax_locales():
    result = []
    for id, lang in LANGUAGES.items():
        result.append({'value': id, 'text': id.upper(), 'subtext': lang})

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
