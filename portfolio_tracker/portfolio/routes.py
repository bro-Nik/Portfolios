import json

from flask import abort, render_template, session, url_for, request
from flask_login import current_user, login_required

from ..general_functions import actions_in
from ..wraps import demo_user_change
from ..wallet.utils import get_wallet_has_asset, last_wallet, \
    last_wallet_transaction
from .models import OtherAsset, db, Ticker
from .utils import Portfolios, create_asset, create_new_transaction, \
    create_other_asset, create_portfolio, create_new_body, get_asset, \
    get_body, get_portfolio, get_ticker, get_transaction
from . import bp


@bp.route('/', methods=['GET', 'POST'])
@login_required
@demo_user_change
def portfolios():
    """Portfolios page and actions on portfolios."""
    # Actions
    if request.method == 'POST':
        actions_in(request.data, get_portfolio)
        db.session.commit()
        return ''

    return render_template('portfolio/portfolios.html',
                           portfolios=Portfolios())


@bp.route('/portfolio_settings', methods=['GET', 'POST'])
@login_required
@demo_user_change
def portfolio_settings():
    """Portfolio settings."""
    portfolio = get_portfolio(request.args.get('portfolio_id')
                              ) or create_portfolio()

    # Apply settings
    if request.method == 'POST':
        portfolio.edit(request.form)
        db.session.commit()
        return ''

    return render_template('portfolio/portfolio_settings.html',
                           portfolio=portfolio)


@bp.route('/<int:portfolio_id>', methods=['GET', 'POST'])
@login_required
@demo_user_change
def portfolio_info(portfolio_id):
    """Portfolio page and actions on assets."""
    portfolio = get_portfolio(portfolio_id) or abort(404)

    # Actions
    if request.method == 'POST':
        actions_in(request.data, get_asset, portfolio=portfolio)
        db.session.commit()
        return ''

    page = 'other_' if portfolio.market == 'other' else ''
    return render_template(f'portfolio/{page}portfolio_info.html',
                           portfolio=portfolio, portfolios=Portfolios())


@bp.route('/<string:market>/add_asset_modal', methods=['GET'])
@login_required
def asset_add_modal(market):
    """Modal window to add asset."""
    return render_template('portfolio/add_asset_modal.html', market=market,
                           portfolio_id=request.args.get('portfolio_id'))


@bp.route('/<string:market>/add_asset_tickers', methods=['GET'])
@login_required
def asset_add_tickers(market):
    """Tickers to modal window to add asset."""
    query = (Ticker.query.filter(Ticker.market == market)
             .order_by(Ticker.market_cap_rank.is_(None),
                       Ticker.market_cap_rank.asc()))

    if search := request.args.get('search'):
        query = query.filter(Ticker.name.contains(search) |
                             Ticker.symbol.contains(search))

    tickers = tuple(query.paginate(page=request.args.get('page', 1, type=int),
                                   per_page=20, error_out=False))
    if not tickers:
        return 'end'

    return render_template('portfolio/add_asset_tickers.html', tickers=tickers)


@bp.route('/add_asset', methods=['GET'])
@login_required
@demo_user_change
def asset_add():
    """Add asset to portfolio."""
    ticker_id = request.args.get('ticker_id')
    portfolio = get_portfolio(request.args.get('portfolio_id')) or abort(404)
    asset = get_asset(portfolio=portfolio, ticker_id=ticker_id)
    if not asset:
        ticker = get_ticker(ticker_id) or abort(404)
        asset = create_asset(portfolio, ticker=ticker)
        db.session.commit()

    return str(url_for('.asset_info',
                       only_content=request.args.get('only_content'),
                       portfolio_id=portfolio.id, asset_id=asset.id))


@bp.route('/asset_settings', methods=['GET', 'POST'])
@login_required
def asset_settings():
    """Asset settings."""
    portfolio = get_portfolio(request.args.get('portfolio_id')) or abort(404)
    asset = get_asset(request.args.get('asset_id'), portfolio)

    # Apply settings
    if request.method == 'POST':
        if not asset and portfolio.market != 'other':
            abort(404)

        asset = asset or create_other_asset(portfolio)
        asset.edit(request.form)
        db.session.commit()
        return ''

    page = 'other_' if portfolio.market == 'other' else ''
    return render_template(f'portfolio/{page}asset_settings.html',
                           asset=asset, portfolio_id=portfolio.id)


@bp.route('/asset_transfer', methods=['GET', 'POST'])
@login_required
def asset_transfer():
    """Asset settings."""
    portfolio = get_portfolio(request.args.get('portfolio_id')) or abort(404)
    asset = get_asset(request.args.get('asset_id'), portfolio) or abort(404)

    # Apply settings
    if request.method == 'POST':
        portfolio2 = get_portfolio(request.form.get('trans_to')) or abort(404)
        asset2 = get_asset(portfolio=portfolio2, ticker_id=asset.ticker_id)

        for transaction in asset.transactions:
            transaction.portfolio_id = portfolio2.id
            if asset2:
                asset.transactions.remove(transaction)
                asset2.transactions.append(transaction)
                transaction.update_dependencies()

        if asset2:
            asset2.comment = f'{asset2.comment or ""}{asset.comment or ""}'
            asset.delete()
        else:
            asset.portfolio_id = portfolio2.id
        db.session.commit()
        return ''

    return render_template('portfolio/asset_transfer.html',
                           asset=asset, portfolio_id=portfolio.id)


@bp.route('/asset_info', methods=['GET', 'POST'])
@login_required
@demo_user_change
def asset_info():
    """Asset page and actions on transactions."""
    portfolio = get_portfolio(request.args.get('portfolio_id')) or abort(404)
    asset = get_asset(request.args.get('asset_id'), portfolio,
                      request.args.get('ticker_id')) or abort(404)

    # Actions
    if request.method == 'POST':
        if request.args.get('bodies'):
            actions_in(request.data, get_body, asset=asset)
            session['other_asset_page'] = 'bodies'
        else:
            actions_in(request.data, get_transaction, asset=asset)
        db.session.commit()
        return ''

    portfolio.update_price()

    page = 'other_' if portfolio.market == 'other' else ''
    return render_template(f'portfolio/{page}asset_info.html', asset=asset)


@bp.route('/transaction_info', methods=['GET', 'POST'])
@login_required
@demo_user_change
def transaction_info():
    """Transaction info."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(request.args.get('asset_id'), portfolio,
                      request.args.get('ticker_id')) or abort(404)
    transaction = get_transaction(request.args.get('transaction_id'), asset
                                  ) or create_new_transaction(asset)

    # Apply transaction
    if request.method == 'POST':
        transaction.update_dependencies('cancel')
        transaction.edit(request.form)
        transaction.update_dependencies()
        db.session.commit()
        return ''

    if isinstance(asset, OtherAsset):
        return render_template('portfolio/other_transaction.html', asset=asset,
                               transaction=transaction)

    asset.free = asset.get_free() - transaction.quantity
    wallets = {'Buy': last_wallet('buy'),
               'Sell': get_wallet_has_asset(asset.ticker_id)}
    if transaction.wallet:
        wallets[transaction.type] = transaction.wallet

    if not transaction.quote_ticker:
        lt = last_wallet_transaction(transaction.wallet or wallets['Buy'],
                                     transaction.type)
        transaction.quote_ticker = lt.quote_ticker if lt else current_user.currency_ticker
    calc_type = session.get('transaction_calculation_type', 'amount')
    return render_template('portfolio/transaction.html',
                           transaction=transaction, asset=asset,
                           wallets=wallets, calculation_type=calc_type)


@bp.route('/other_asset_body', methods=['GET', 'POST'])
@login_required
@demo_user_change
def body_info():
    """Other body info."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(request.args.get('asset_id'), portfolio) or abort(404)
    body = get_body(request.args.get('body_id'), asset) or create_new_body(asset)

    # Apply settings
    if request.method == 'POST':
        body.edit(request.form)
        body.update_dependencies()
        db.session.commit()

        session['other_asset_page'] = 'bodies'
        return ''

    return render_template('portfolio/other_body.html', asset=asset, body=body)


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


@bp.route('/ajax_stable', methods=['GET'])
@login_required
def ajax_stable_assets():
    """Возвращает список стабильных активов."""
    result = []
    tickers = db.session.execute(
        db.select(Ticker).filter_by(stable=True)).scalars()

    for ticker in tickers:
        result.append({'value': ticker.id, 'text': ticker.symbol.upper()})
    if not result:
        result = {'message': 'Нет тикеров'}

    return json.dumps(result)
