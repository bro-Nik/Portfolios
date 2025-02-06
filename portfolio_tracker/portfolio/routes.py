from flask import abort, render_template, session, url_for, request
from flask_login import current_user as user, login_required

from ..services import user_object_search_engine as ose
from ..general_functions import actions_on_objects
from ..wraps import closed_for_demo_user
from .models import OtherAsset
from .repository import TickerRepository
from .services.portfolios import Portfolios
from . import bp


@bp.route('/', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def portfolios():
    """Portfolios page and actions on portfolios."""
    # Actions
    if request.method == 'POST':
        actions_on_objects(request.data, user.service.get_portfolio)
        return ''

    return render_template('portfolio/portfolios.html',
                           portfolios=Portfolios(user))  # type: ignore


@bp.route('/portfolio_settings', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def portfolio_settings():
    """Portfolio settings."""
    portfolio = ose.get_portfolio(**request.args, create=True) or abort(404)

    # Apply settings
    if request.method == 'POST':
        portfolio.service.edit(request.form)
        return ''

    return render_template('portfolio/portfolio_settings.html',
                           portfolio=portfolio)


@bp.route('/<int:portfolio_id>', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def portfolio_info(portfolio_id):
    """Portfolio page and actions on assets."""
    portfolio = ose.get_portfolio(portfolio_id) or abort(404)

    # Actions
    if request.method == 'POST':
        actions_on_objects(request.data, portfolio.service.get_asset)
        return ''

    page = 'other_' if portfolio.market == 'other' else ''
    return render_template(f'portfolio/{page}portfolio_info.html',
                           portfolio=portfolio,
                           portfolios=Portfolios(user))  # type: ignore


@bp.route('/asset_add', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_add():
    """Modal window to add asset."""
    if request.method == 'POST':
        # Add asset to portfolio
        asset = ose.get_portfolio_asset(**request.args, create=True) or abort(404)

        return str(url_for('.asset_info',
                           only_content=request.args.get('only_content'),
                           portfolio_id=asset.portfolio_id, asset_id=asset.id))

    return render_template('portfolio/add_asset_modal.html',
                           market=request.args.get('market'),
                           portfolio_id=request.args.get('portfolio_id'))


@bp.route('/<string:market>/add_asset_tickers', methods=['GET'])
@login_required
def asset_add_tickers(market):
    """Tickers to modal window to add asset."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    tickers = TickerRepository.get_with_market_paginate(market, search, page)

    if not tickers:
        return 'end'

    return render_template('portfolio/add_asset_tickers.html', tickers=tickers)


@bp.route('/asset_settings', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_settings():
    """Asset settings."""
    asset = ose.get_portfolio_asset(**request.args, create=True) or abort(404)

    # Apply settings
    if request.method == 'POST':
        asset.service.edit(request.form)
        return ''

    page = 'other_' if asset.portfolio.market == 'other' else ''
    return render_template(f'portfolio/{page}asset_settings.html',
                           asset=asset, portfolio_id=asset.portfolio_id)


@bp.route('/asset_transfer', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_transfer():
    """Asset settings."""
    asset = ose.get_portfolio_asset(**request.args) or abort(404)

    # Apply settings
    if request.method == 'POST':
        asset.service.move_asset_to(portfolio_id=request.form.get('trans_to'))
        return ''

    return render_template('portfolio/asset_transfer.html',
                           asset=asset, portfolio_id=asset.portfolio_id)


@bp.route('/asset_info', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_info():
    """Asset page and actions on transactions."""
    asset = ose.get_portfolio_asset(**request.args) or abort(404)

    # Actions
    if request.method == 'POST':
        if request.args.get('bodies') and isinstance(asset, OtherAsset):
            actions_on_objects(request.data, asset.service.get_body)
            session['other_asset_page'] = 'bodies'
        else:
            actions_on_objects(request.data, asset.service.get_transaction)
        return ''

    asset.portfolio.service.update_info()

    page = 'other_' if asset.portfolio.market == 'other' else ''
    return render_template(f'portfolio/{page}asset_info.html', asset=asset)


@bp.route('/transaction_info', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def transaction_info():
    """Transaction info."""
    transaction = ose.get_portfolio_transaction(**request.args, create=True) or abort(404)

    # Apply transaction
    if request.method == 'POST':
        transaction.service.edit(request.form)
        return ''

    if transaction.portfolio.market == 'other':
        return render_template('portfolio/other_transaction.html',
                               asset=transaction.asset,
                               transaction=transaction)

    calc_type = session.get('transaction_calculation_type', 'amount')
    return render_template('portfolio/transaction.html',
                           transaction=transaction, asset=transaction.portfolio_asset,
                           calculation_type=calc_type)


@bp.route('/other_asset_body', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def body_info():
    """Other body info."""
    body = ose.get_body(**request.args, create=True) or abort(404)

    # Apply settings
    if request.method == 'POST':
        body.service.edit(request.form)
        session['other_asset_page'] = 'bodies'
        return ''

    return render_template('portfolio/other_body.html',
                           asset=body.asset, body=body)


@bp.route('/change_table_sort', methods=['GET'])
@login_required
def change_table_sort():
    """Изменение пользовательской сортировки таблицы."""
    tab_name = request.args.get('tab_name')
    field = request.args.get('field')
    sort_order = request.args.get('sort_order')

    session[tab_name] = {'field': field, 'sort_order': sort_order}
    return ''


@bp.route('/change_session_param', methods=['GET'])
@login_required
def change_session_param():
    """Шаблонная функции изменения параметров в сессии."""
    name = request.args.get('name')
    value = request.args.get('value')

    session[name] = value
    return ''
