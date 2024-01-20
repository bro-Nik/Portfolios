import json
from datetime import datetime, timezone

from flask import abort, render_template, session, url_for, request
from flask_login import current_user, login_required

from ..wraps import demo_user_change
from ..wallet.utils import get_transaction, get_wallet_has_asset, \
    last_wallet, last_wallet_transaction
from . import bp
from .models import db, Ticker, OtherTransaction, OtherBody, Transaction
from .utils import AllPortfolios, get_other_body, get_other_transaction, \
    get_portfolio, create_new_other_transaction, \
    actions_on_assets, actions_on_other_assets, actions_on_other_body, \
    actions_on_other_transactions, actions_on_portfolios, \
    actions_on_transactions, create_new_other_asset, create_new_other_body, \
    create_new_portfolio, create_new_transaction, get_asset, get_other_asset


@bp.route('/', methods=['GET'])
@login_required
def portfolios():
    """Portfolios page."""
    all_portfolios = AllPortfolios()
    all_portfolios.update_price()
    return render_template('portfolio/portfolios.html',
                           all_portfolios=all_portfolios)


@bp.route('/action', methods=['POST'])
@login_required
@demo_user_change
def portfolios_action():
    """Action portfolio."""
    data = json.loads(request.data) if request.data else {}

    actions_on_portfolios(data['ids'], data['action'])
    return ''


@bp.route('/portfolio_settings', methods=['GET'])
@login_required
def portfolio_settings():
    """Portfolio settings."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    return render_template('portfolio/portfolio_settings.html',
                           portfolio=portfolio)


@bp.route('/portfolio_settings_update', methods=['POST'])
@login_required
@demo_user_change
def portfolio_settings_update():
    """Portfolio settings update."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    if not portfolio:
        portfolio = create_new_portfolio(request.form)

    portfolio.edit(request.form)
    return ''


@bp.route('/<int:portfolio_id>', methods=['GET'])
@login_required
def portfolio_info(portfolio_id):
    """Portfolio page."""
    portfolio = get_portfolio(portfolio_id) or abort(404)

    all_portfolios = AllPortfolios()
    all_portfolios.update_price()

    page = 'other_' if portfolio.market == 'other' else ''
    return render_template(f'portfolio/{page}portfolio_info.html',
                           portfolio=portfolio, all_portfolios=all_portfolios)


@bp.route('/assets_action', methods=['POST'])
@login_required
@demo_user_change
def assets_action():
    """Asset action."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    data = json.loads(request.data) if request.data else {}

    actions_on_assets(portfolio, data['ids'], data['action'])
    return ''


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
        query = query.filter(Ticker.name.contains(search) or
                             Ticker.symbol.contains(search))

    tickers = tuple(query.paginate(page=request.args.get('page', 1, type=int),
                                   per_page=20, error_out=False))
    if tickers:
        return render_template('portfolio/add_asset_tickers.html',
                               tickers=tickers)
    return 'end'


@bp.route('/add_asset', methods=['GET'])
@login_required
@demo_user_change
def asset_add():
    """Add asset to portfolio."""
    ticker_id = request.args.get('ticker_id')
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(portfolio, ticker_id=ticker_id, create=True)

    return str(url_for('.asset_info',
                       only_content=request.args.get('only_content'),
                       portfolio_id=asset.portfolio_id,
                       ticker_id=asset.ticker_id)) if asset else abort(404)


@bp.route('/asset_settings', methods=['GET'])
@login_required
def asset_settings():
    """Asset settings."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(portfolio, request.args.get('ticker_id')) or abort(404)
    return render_template('portfolio/asset_settings.html', asset=asset)


@bp.route('/asset_settings_update', methods=['POST'])
@login_required
@demo_user_change
def asset_settings_update():
    """Asset settings update."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(portfolio, request.args.get('ticker_id')) or abort(404)
    asset.edit(request.form)
    return ''


@bp.route('/asset_info')
@login_required
def asset_info():
    """Asset page."""
    portfolio = get_portfolio(request.args.get('portfolio_id')) or abort(404)

    if portfolio.market != 'other':
        asset = get_asset(portfolio, request.args.get('ticker_id')) or abort(404)
    else:
        asset = get_other_asset(portfolio, request.args.get('asset_id')) or abort(404)

    asset.portfolio.update_price()
    asset.update_details()

    page = 'other_' if portfolio.market == 'other' else ''
    return render_template(f'portfolio/{page}asset_info.html', asset=asset)


@bp.route('/transaction_action', methods=['POST'])
@login_required
@demo_user_change
def transactions_action():
    """Transactions action."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(portfolio, request.args.get('ticker_id'))
    data = json.loads(request.data) if request.data else {}

    actions_on_transactions(asset, data['ids'], data['action'])
    return ''


@bp.route('/transaction_info')
@login_required
def transaction_info():
    """Transaction info."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(portfolio, request.args.get('ticker_id')) or abort(404)

    asset.update_price()
    asset.free = asset.get_free()
    transaction = get_transaction(asset, request.args.get('transaction_id'))

    wallet_buy = wallet_sell = None
    if transaction:
        if transaction.type == 'Buy':
            wallet_buy = transaction.wallet
        else:
            wallet_sell = transaction.wallet

        if transaction.order and transaction.type == 'Sell':
            asset.free -= transaction.quantity
    else:
        transaction = Transaction(type='Buy', date=datetime.now(timezone.utc),
                                  price=asset.price)

    if not wallet_buy:
        wallet_buy = last_wallet('buy')
    if not wallet_sell:
        wallet_sell = get_wallet_has_asset(asset.ticker_id)

    if not transaction.quote_ticker:
        last_transaction = last_wallet_transaction(transaction.wallet or
                                                   wallet_buy,
                                                   transaction.type)
        if last_transaction:
            transaction.quote_ticker = last_transaction.quote_ticker
        else:
            transaction.quote_ticker = current_user.currency_ticker

    calculation_type = session.get('transaction_calculation_type', 'amount')
    return render_template('portfolio/transaction.html',
                           transaction=transaction, asset=asset,
                           wallet_buy=wallet_buy, wallet_sell=wallet_sell,
                           calculation_type=calculation_type)


@bp.route('/transaction_update', methods=['POST'])
@login_required
@demo_user_change
def transaction_update():
    """Add transaction or change transaction info."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_asset(portfolio, request.args.get('ticker_id')) or abort(404)

    transaction = get_transaction(asset, request.args.get('transaction_id'))
    if transaction:
        transaction.update_dependencies('cancel')
    else:
        transaction = create_new_transaction(asset)

    transaction.edit(request.form)
    transaction.update_dependencies()
    return ''


# Other assets

@bp.route('/other_asset_action', methods=['POST'])
@login_required
@demo_user_change
def other_asset_action():
    """Other assets action."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    data = json.loads(request.data) if request.data else {}

    actions_on_other_assets(portfolio, data['ids'], data['action'])
    return ''


@bp.route('/other_asset/transaction_action', methods=['POST'])
@login_required
def other_transaction_action():
    """Other transaction action."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id'))
    data = json.loads(request.data) if request.data else {}

    actions_on_other_transactions(asset, data['ids'], data['action'])
    session['other_asset_page'] = 'transactions'
    return ''


@bp.route('/other_asset/body_action', methods=['POST'])
@login_required
def other_body_action():
    """Other body action."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id'))
    data = json.loads(request.data) if request.data else {}

    actions_on_other_body(asset, data['ids'], data['action'])
    session['other_asset_page'] = 'bodies'
    return ''


@bp.route('/<int:portfolio_id>/other_asset_settings', methods=['GET'])
@login_required
def other_asset_settings(portfolio_id):
    """Other asset settings."""
    portfolio = get_portfolio(portfolio_id)
    asset = get_other_asset(portfolio, request.args.get('asset_id'))
    return render_template('portfolio/other_asset_settings.html', asset=asset,
                           portfolio_id=portfolio_id)


@bp.route('/other_asset_update', methods=['POST'])
@login_required
@demo_user_change
def other_asset_settings_update():
    """Other asset settings update."""
    portfolio = get_portfolio(request.args.get('portfolio_id')) or abort(404)

    asset = get_other_asset(portfolio, request.args.get('asset_id'))
    if not asset:
        asset = create_new_other_asset(portfolio)

    asset.edit(portfolio, request.form)
    return ''


@bp.route('/other_asset_transaction', methods=['GET'])
@login_required
def other_transaction():
    """Other transaction info."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id')) or abort(404)

    transaction = get_other_transaction(asset,
                                        request.args.get('transaction_id'))

    if not transaction:
        transaction = OtherTransaction(type='Profit',
                                       date=datetime.now(timezone.utc))

        if asset.transactions:
            transaction.amount_ticker = asset.transactions[-1].amount_ticker
        else:
            transaction.amount_ticker = current_user.currency_ticker

    return render_template('portfolio/other_transaction.html',
                           asset=asset, transaction=transaction)


@bp.route('/other_asset_transaction_update', methods=['POST'])
@login_required
@demo_user_change
def other_transaction_update():
    """Other transaction info update."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id')) or abort(404)

    transaction = get_other_transaction(asset,
                                        request.args.get('transaction_id'))
    if transaction:
        transaction.update_dependencies('cancel')
    else:
        transaction = create_new_other_transaction(asset)

    transaction.edit(request.form)
    transaction.update_dependencies()
    db.session.commit()
    session['other_asset_page'] = 'transactions'
    return ''


@bp.route('/other_asset_body', methods=['GET'])
@login_required
def other_body():
    """Other body info."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id')) or abort(404)

    body = get_other_body(asset, request.args.get('body_id'))
    if not body:
        body = OtherBody(date=datetime.now(timezone.utc))

        if asset.bodies:
            body.amount_ticker = asset.bodies[-1].amount_ticker
            body.cost_now_ticker = asset.bodies[-1].cost_now_ticker
        else:
            body.amount_ticker = current_user.currency_ticker
            body.cost_now_ticker = current_user.currency_ticker

    return render_template('portfolio/other_body.html', asset=asset, body=body)


@bp.route('/other_asset_body_update', methods=['POST'])
@login_required
@demo_user_change
def other_body_update():
    """Other body info update."""
    portfolio = get_portfolio(request.args.get('portfolio_id'))
    asset = get_other_asset(portfolio, request.args.get('asset_id')) or abort(404)

    body = get_other_body(asset, request.args.get('body_id'))
    if body:
        body.update_dependencies('cancel')
    else:
        body = create_new_other_body(asset)

    body.edit(request.form)
    body.update_dependencies()
    db.session.commit()
    session['other_asset_page'] = 'bodies'
    return ''


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
