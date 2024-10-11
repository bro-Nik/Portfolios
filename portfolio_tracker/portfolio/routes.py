import json

from flask import abort, render_template, session, url_for, request
from flask_login import current_user, login_required

from ..general_functions import actions_in
from ..wraps import closed_for_demo_user
from ..wallet.models import Wallet
from .models import db, OtherAsset, Portfolio, Ticker
from .utils import Portfolios
from . import bp


@bp.route('/', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def portfolios():
    """Portfolios page and actions on portfolios."""
    # Actions
    if request.method == 'POST':
        actions_in(request.data, Portfolio.get)
        db.session.commit()
        return ''

    return render_template('portfolio/portfolios.html',
                           portfolios=Portfolios())


@bp.route('/portfolio_settings', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def portfolio_settings():
    """Portfolio settings."""
    portfolio = Portfolio.get(request.args.get('portfolio_id')
                              ) or Portfolio.create()

    # Apply settings
    if request.method == 'POST':
        if not portfolio.id:
            current_user.portfolios.append(portfolio)

        portfolio.edit(request.form)
        db.session.commit()
        return ''

    return render_template('portfolio/portfolio_settings.html',
                           portfolio=portfolio)


@bp.route('/<int:portfolio_id>', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def portfolio_info(portfolio_id):
    """Portfolio page and actions on assets."""
    portfolio = Portfolio.get(portfolio_id) or abort(404)

    # Actions
    if request.method == 'POST':
        actions_in(request.data, portfolio.get_asset)
        db.session.commit()
        return ''

    page = 'other_' if portfolio.market == 'other' else ''
    return render_template(f'portfolio/{page}portfolio_info.html',
                           portfolio=portfolio, portfolios=Portfolios())


@bp.route('/asset_add', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_add():
    """Modal window to add asset."""
    portfolio_id = request.args.get('portfolio_id')
    market = request.args.get('market')

    if request.method == 'POST':
        # Add asset to portfolio
        portfolio = Portfolio.get(portfolio_id) or abort(404)
        ticker_id = request.args.get('ticker_id')
        asset = portfolio.get_asset(ticker_id)
        if not asset:
            ticker = Ticker.get(ticker_id) or abort(404)
            if ticker.market != portfolio.market:
                abort(404)

            asset = portfolio.create_asset(ticker)
            portfolio.assets.append(asset)
            db.session.commit()

        return str(url_for('.asset_info',
                           only_content=request.args.get('only_content'),
                           portfolio_id=portfolio.id, asset_id=asset.id))

    return render_template('portfolio/add_asset_modal.html', market=market,
                           portfolio_id=portfolio_id)


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


@bp.route('/asset_settings', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_settings():
    """Asset settings."""
    portfolio = Portfolio.get(request.args.get('portfolio_id')) or abort(404)
    find_by = request.args.get('ticker_id') or request.args.get('asset_id')
    asset = portfolio.get_asset(find_by)

    # Apply settings
    if request.method == 'POST':
        if not asset:
            if portfolio.market == 'other':
                asset = portfolio.create_other_asset()
                portfolio.other_assets.append(asset)
            else:
                abort(404)

        asset.edit(request.form)
        db.session.commit()
        return ''

    page = 'other_' if portfolio.market == 'other' else ''
    return render_template(f'portfolio/{page}asset_settings.html',
                           asset=asset, portfolio_id=portfolio.id)


@bp.route('/asset_transfer', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def asset_transfer():
    """Asset settings."""
    portfolio = Portfolio.get(request.args.get('portfolio_id')) or abort(404)
    find_by = request.args.get('ticker_id') or request.args.get('asset_id')
    asset = portfolio.get_asset(find_by) or abort(404)

    # Apply settings
    if request.method == 'POST':
        portfolio2 = Portfolio.get(request.form.get('trans_to')) or abort(404)
        asset2 = portfolio2.get_asset(asset.ticker_id)

        for transaction in asset.transactions:
            transaction.portfolio_id = portfolio2.id
            if asset2:
                asset.transactions.remove(transaction)
                asset2.transactions.append(transaction)
                transaction.update_dependencies()

        if asset2:
            while asset.alerts:
                alert = asset.alerts.pop()
                alert.asset_id = asset2.id
                asset2.alerts.append(alert)

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
@closed_for_demo_user(['POST'])
def asset_info():
    """Asset page and actions on transactions."""
    portfolio = Portfolio.get(request.args.get('portfolio_id')) or abort(404)
    find_by = request.args.get('ticker_id') or request.args.get('asset_id')
    asset = portfolio.get_asset(find_by) or abort(404)

    # Actions
    if request.method == 'POST':
        if request.args.get('bodies'):
            actions_in(request.data, asset.get_body)
            session['other_asset_page'] = 'bodies'
        else:
            actions_in(request.data, asset.get_transaction)
        db.session.commit()
        return ''

    portfolio.update_info()

    page = 'other_' if portfolio.market == 'other' else ''
    return render_template(f'portfolio/{page}asset_info.html', asset=asset)


@bp.route('/transaction_info', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def transaction_info():
    """Transaction info."""
    if request.args.get('portfolio_id'):
        w_or_p = Portfolio.get(request.args.get('portfolio_id')) or abort(404)
    elif request.args.get('wallet_id'):
        w_or_p = Wallet.get(request.args.get('wallet_id')) or abort(404)
    find_by = request.args.get('ticker_id') or request.args.get('asset_id')
    asset = w_or_p.get_asset(find_by) or abort(404)
    transaction = asset.get_transaction(request.args.get('transaction_id')
                                        ) or asset.create_transaction()
    if not transaction.base_ticker:
        transaction.base_ticker = asset.ticker

    # Apply transaction
    if request.method == 'POST':
        if not transaction.id:
            asset.transactions.append(transaction)

        transaction.edit(request.form)
        transaction.update_dependencies()

        if transaction.type in ('TransferOut', 'TransferIn'):
            transaction.update_related_transaction(Portfolio, request.form.get('portfolio_id'))
        db.session.commit()
        return ''

    if isinstance(asset, OtherAsset):
        return render_template('portfolio/other_transaction.html', asset=asset,
                               transaction=transaction)

    # asset.free = asset.get_free() - transaction.quantity
    wallets = {'Buy': Wallet.last('buy'),
               'Sell': Wallet.get_has_asset(asset.ticker_id)}
    if transaction.wallet:
        wallets[transaction.type] = transaction.wallet

    # if not transaction.quote_ticker:
    #     wallet = transaction.wallet or wallets['Buy']
    #     lt = wallet.last_transaction(transaction.type)
    #     transaction.quote_ticker = lt.quote_ticker if lt else current_user.currency_ticker
    calc_type = session.get('transaction_calculation_type', 'amount')
    return render_template('portfolio/transaction.html',
                           transaction=transaction, asset=asset,
                           wallets=wallets, calculation_type=calc_type)


@bp.route('/other_asset_body', methods=['GET', 'POST'])
@login_required
@closed_for_demo_user(['POST'])
def body_info():
    """Other body info."""
    portfolio = Portfolio.get(request.args.get('portfolio_id')) or abort(404)
    asset = portfolio.get_asset(request.args.get('asset_id')) or abort(404)
    body = asset.get_body(request.args.get('body_id')) or asset.create_body()

    # Apply settings
    if request.method == 'POST':
        if not body.id:
            asset.bodies.append(body)

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
