from datetime import datetime, timezone

from portfolio_tracker.app import db
from portfolio_tracker.general_functions import from_user_datetime
from portfolio_tracker.portfolio.models import Asset, Transaction
from portfolio_tracker.portfolio.repository import PortfolioRepository, TickerRepository, TransactionRepository
from portfolio_tracker.wallet.repository import WalletRepository
from portfolio_tracker.watchlist.services.alert import update_alert


class TransactionService:

    def __init__(self, transaction: Transaction) -> None:
        self.transaction = transaction

    def edit(self, form: dict) -> None:

        # Отменить, если есть прошлые изменения
        self.update_dependencies('cancel')

        type = form.get('type', '')
        # Направление сделки (direction)
        d = 1 if type in ('Buy', 'Input', 'TransferIn', 'Earning') else -1

        self.transaction.type = type
        self.transaction.date = from_user_datetime(form.get('date', ''))
        self.transaction.comment = form.get('comment', '')


        if type in ('Buy', 'Input', 'Earning'):
            self.transaction.wallet_id = form['buy_wallet_id']
        elif type in ('Sell', 'Output'):
            self.transaction.wallet_id = form['sell_wallet_id']

        if self.transaction.type in ('Buy', 'Sell'):
            self.transaction.ticker2_id = form.get(type.lower() + '_ticker2_id')
            self.transaction.price = float(form['price'])

            quote_ticker = TickerRepository.get(self.transaction.ticker2_id)
            if not quote_ticker:
                return

            self.transaction.price_usd = self.transaction.price * quote_ticker.price
            self.transaction.order = bool(form.get('order'))
            if form.get('quantity') is not None:
                self.transaction.quantity = float(form['quantity']) * d
                self.transaction.quantity2 = self.transaction.price * self.transaction.quantity * -1
            else:
                self.transaction.quantity2 = float(form['quantity2']) * d * -1
                self.transaction.quantity = self.transaction.quantity2 / self.transaction.price * -1

        # Wallet transaction
        elif self.transaction.type in ('Input', 'Output', 'Earning'):
            self.transaction.quantity = float(form['quantity']) * d

        elif self.transaction.type in ('TransferIn', 'TransferOut'):
            self.transaction.quantity = float(form['quantity']) * d
            self.transaction.wallet2_id = form.get('buy_wallet_id')
            self.transaction.portfolio2_id = form.get('portfolio_id')

        # Уведомление
        update_alert(self.transaction.alert, self.transaction)

        self.update_dependencies()
        self.update_related_transaction()
        TransactionRepository.save(self.transaction)


    def update_dependencies(self, param: str = '') -> None:
        t = self.transaction

        # Направление сделки (direction)
        d = -1 if param == 'cancel' else 1

        wallet = WalletRepository.get(t.wallet_id)
        portfolio = PortfolioRepository.get(t.portfolio_id)

        # Базовый актив портфеля
        p_asset1 = get_or_create_asset(portfolio, t.ticker_id)
        # Котируемый актив портфеля
        p_asset2 = get_or_create_asset(portfolio, t.ticker2_id)
        # Базовый актив кошелька
        w_asset1 = get_or_create_asset(wallet, t.ticker_id)
        # Котируемый актив кошелька
        w_asset2 = get_or_create_asset(wallet, t.ticker2_id)

        if t.type in ('Buy', 'Sell'):
            if not (p_asset1 and p_asset2 and w_asset1 and w_asset2):
                return

            # Ордер
            if t.order:
                if t.type == 'Buy':
                    p_asset1.buy_orders += t.quantity * t.price_usd * d
                    p_asset2.sell_orders -= t.quantity2 * d
                    w_asset1.buy_orders += t.quantity * t.price_usd * d
                    w_asset2.sell_orders -= t.quantity2 * d
                elif t.type == 'Sell':
                    w_asset1.sell_orders -= t.quantity * d
                    p_asset1.sell_orders -= t.quantity * d

            # Не ордер
            else:
                p_asset1.amount += t.quantity * t.price_usd * d
                p_asset1.quantity += t.quantity * d
                p_asset2.amount += t.quantity2 * p_asset2.price * d
                p_asset2.quantity += t.quantity2 * d

                w_asset1.quantity += t.quantity * d
                w_asset2.quantity += t.quantity2 * d

        elif t.type in ('Earning'):
            if not (p_asset1 and w_asset1):
                return

            p_asset1.quantity += t.quantity * d
            w_asset1.quantity += t.quantity * d

        else:
            if portfolio and p_asset1:
                p_asset1.amount += t.quantity * d
                p_asset1.quantity += t.quantity * d
            if wallet and w_asset1:
                w_asset1.quantity += t.quantity * d

    def update_related_transaction(self, param: str = '') -> None:
        t = self.transaction

        if t.type in ('TransferOut', 'TransferIn'):
            if param == 'cancel':
                if t.related_transaction:
                    t2 = t.related_transaction
                    t.related_transaction = None
                    t2.related_transaction = None
                    t2.service.delete()
            else:
                wallet2 = WalletRepository.get(getattr(t, 'wallet2_id', None))
                portfolio2 = PortfolioRepository.get(getattr(t, 'portfolio2_id', None))

                # Связанная транзакция
                asset2 = get_or_create_asset(portfolio2 or wallet2, t.ticker_id)

                if asset2:
                    t2 = t.related_transaction
                    if not t2:
                        t2 = asset2.service.create_transaction()
                        t.related_transaction = t2

                    t2.service.edit({
                        'type': 'TransferOut' if t.type == 'TransferIn' else 'TransferIn',
                        'date': t.date,
                        'quantity': t.quantity * -1
                    })

                    db.session.flush()
                    t.related_transaction_id = t2.id
                    t2.related_transaction_id = t.id

                    TransactionRepository.save(t)
                    TransactionRepository.save(t2)

    def convert_order_to_transaction(self) -> None:
        self.update_dependencies('cancel')

        t = self.transaction
        t.order = False
        t.date = datetime.now(timezone.utc)
        if t.alert:
            t.alert.transaction_id = None
            t.alert.service.delete()
        self.update_dependencies()

    def delete(self) -> None:
        self.update_dependencies('cancel')
        TransactionRepository.delete(self.transaction)


def get_or_create_asset(parent, ticker_id) -> Asset | None:
    if parent and ticker_id:
        asset = parent.service.get_asset(ticker_id)
        if not asset:
            asset = parent.service.create_asset(ticker_id)
        return asset
