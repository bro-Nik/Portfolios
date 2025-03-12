from datetime import datetime
import unittest

from tests import app, db
from portfolio_tracker.wallet.models import Wallet, WalletAsset
from portfolio_tracker.portfolio.models import Asset, Portfolio, Ticker, Transaction


class TestTransactionService(unittest.TestCase):
    """Класс для тестирования методов транзакций"""

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Создаем тестовые данные
        self.wallet = Wallet(id=1, user_id=1, name='Name')
        self.portfolio = Portfolio(id=1, user_id=1, market='crypto', name='Test Portfolio')
        db.session.add_all([self.wallet, self.portfolio])

        self.btc = Ticker(id='btc', name='Bitcoin', price=26000, symbol='btc', market='crypto')
        self.usdt = Ticker(id='usdt', name='Tether', price=0.9, symbol='usdt', market='crypto')
        db.session.add_all([self.btc, self.usdt])

        self.portfolio_btc = Asset(id=1, portfolio_id=1, ticker_id='btc', quantity=10, amount=500000)
        self.portfolio_usdt = Asset(id=2, portfolio_id=1, ticker_id='usdt', quantity=0, amount=0)
        self.wallet_btc = WalletAsset(id=1, wallet_id=1, ticker_id='btc', quantity=0)
        self.wallet_usdt = WalletAsset(id=2, wallet_id=1, ticker_id='usdt', quantity=5)
        db.session.add_all([self.portfolio_btc, self.portfolio_usdt, self.wallet_btc, self.wallet_usdt])


        # Транзакция
        self.transaction = Transaction(id=1, wallet_id=1, portfolio_id=1,
                                       quantity=0, quantity2=0, price=0,
                                       price_usd=0, type='Buy')
        self.portfolio_btc.transactions = [self.transaction]

        self.date = datetime.now()

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit(self):
        form = {
            'type': 'Sell',
            'date': '2023-10-01T12:00',
            'quantity': 2,
            'price': 51000,
            'sell_wallet_id': 1,
            'sell_ticker2_id': 'usdt',
            'comment': 'New Comment'
        }
        self.transaction.service.edit(form)

        self.assertEqual(self.transaction.type, 'Sell')
        self.assertEqual(self.transaction.quantity, -2)
        self.assertEqual(self.transaction.price, 51000)
        self.assertEqual(self.transaction.wallet_id, 1)
        self.assertEqual(self.transaction.ticker_id, 'btc')
        self.assertEqual(self.transaction.ticker2_id, 'usdt')
        self.assertEqual(self.transaction.comment, 'New Comment')

    def test_update_dependencies_create_assets(self):
        db.session.add_all([
            Ticker(id='eth', name='ETH', price=2600, symbol='eth', market='crypto'),
            Ticker(id='busd', name='BUSD', price=1, symbol='busd', market='crypto'),
        ])
        db.session.commit()

        transaction = Transaction(type="Buy",
                                  quantity=1,
                                  quantity2=-2,
                                  price=50000,
                                  price_usd=50000,
                                  wallet_id=1,
                                  portfolio_id=1,
                                  ticker_id='eth',
                                  ticker2_id='busd')
        transaction.service.update_dependencies()
        db.session.add(transaction)
        db.session.commit()

        # Проверяем, что активы созданны
        for ticker_id in ('eth', 'busd'):
            for c in (Asset, WalletAsset):
                asset = db.session.execute(db.select(c).filter_by(ticker_id=ticker_id)).scalar()
                self.assertIsNotNone(asset)

    def test_update_dependencies_buy(self):
        transaction = Transaction(type="Buy",
                                  quantity=1,
                                  quantity2=-2,
                                  price=50000,
                                  price_usd=50000,
                                  wallet_id=1,
                                  portfolio_id=1,
                                  ticker_id='btc',
                                  ticker2_id='usdt')

        transaction.service.update_dependencies()

        # Проверяем, что активы обновлены
        self.assertEqual(self.portfolio_btc.quantity, 11)
        self.assertEqual(self.portfolio_usdt.quantity, -2)
        self.assertEqual(self.portfolio_btc.amount, 550000)
        self.assertEqual(self.portfolio_usdt.amount, -1.8)
        self.assertEqual(self.wallet_btc.quantity, 1)
        self.assertEqual(self.wallet_usdt.quantity, 3)

        transaction.service.update_dependencies('cancel')

        # Проверяем, что активы откатились
        self.assertEqual(self.portfolio_btc.quantity, 10)
        self.assertEqual(self.portfolio_usdt.quantity, 0)
        self.assertEqual(self.portfolio_btc.amount, 500000)
        self.assertEqual(self.portfolio_usdt.amount, 0)
        self.assertEqual(self.wallet_btc.quantity, 0)
        self.assertEqual(self.wallet_usdt.quantity, 5)

    def test_update_dependencies_sell(self):
        transaction = Transaction(type="Sell",
                                  quantity=-1,
                                  quantity2=2,
                                  price=50000,
                                  price_usd=50000,
                                  wallet_id=1,
                                  portfolio_id=1,
                                  ticker_id='btc',
                                  ticker2_id='usdt')

        transaction.service.update_dependencies()

        # Проверяем, что активы обновлены
        self.assertEqual(self.portfolio_btc.quantity, 9)
        self.assertEqual(self.portfolio_usdt.quantity, 2)
        self.assertEqual(self.portfolio_btc.amount, 450000)
        self.assertEqual(self.portfolio_usdt.amount, 1.8)
        self.assertEqual(self.wallet_btc.quantity, -1)
        self.assertEqual(self.wallet_usdt.quantity, 7)

        transaction.service.update_dependencies('cancel')

        # Проверяем, что активы откатились
        self.assertEqual(self.portfolio_btc.quantity, 10)
        self.assertEqual(self.portfolio_usdt.quantity, 0)
        self.assertEqual(self.portfolio_btc.amount, 500000)
        self.assertEqual(self.portfolio_usdt.amount, 0)
        self.assertEqual(self.wallet_btc.quantity, 0)
        self.assertEqual(self.wallet_usdt.quantity, 5)

    def test_update_dependencies_buy_order(self):
        transaction = Transaction(type="Buy",
                                  quantity=1,
                                  quantity2=1,
                                  price=50000,
                                  price_usd=50000,
                                  wallet_id=1,
                                  portfolio_id=1,
                                  ticker_id='btc',
                                  ticker2_id='usdt',
                                  order=True)
        transaction.service.update_dependencies()

        # Проверяем, что активы обновлены
        self.assertEqual(self.portfolio_btc.quantity, 10)
        self.assertEqual(self.portfolio_usdt.quantity, 0)
        self.assertEqual(self.portfolio_btc.amount, 500000)
        self.assertEqual(self.portfolio_usdt.amount, 0)
        self.assertEqual(self.wallet_btc.quantity, 0)
        self.assertEqual(self.wallet_usdt.quantity, 5)
        self.assertEqual(self.portfolio_btc.buy_orders, 50000)
        self.assertEqual(self.portfolio_usdt.sell_orders, -1)
        self.assertEqual(self.wallet_btc.buy_orders, 50000)
        self.assertEqual(self.wallet_usdt.sell_orders, -1)

    def test_update_dependencies_sell_order(self):
        transaction = Transaction(type="Sell",
                                  quantity=1,
                                  quantity2=1,
                                  price=50000,
                                  price_usd=50000,
                                  wallet_id=1,
                                  portfolio_id=1,
                                  ticker_id='btc',
                                  ticker2_id='usdt',
                                  order=True)
        transaction.service.update_dependencies()

        # Проверяем, что ордера обновлены
        self.assertEqual(self.portfolio_btc.quantity, 10)
        self.assertEqual(self.portfolio_usdt.quantity, 0)
        self.assertEqual(self.portfolio_btc.amount, 500000)
        self.assertEqual(self.portfolio_usdt.amount, 0)
        self.assertEqual(self.wallet_btc.quantity, 0)
        self.assertEqual(self.wallet_usdt.quantity, 5)
        self.assertEqual(self.portfolio_btc.sell_orders, -1)
        self.assertEqual(self.wallet_btc.sell_orders, -1)

    def test_update_dependencies_input(self):
        transaction = Transaction(type="Input",
                                  quantity=1,
                                  wallet_id=1,
                                  portfolio_id=1,
                                  ticker_id='usdt')
        transaction.service.update_dependencies()

        # Проверяем, что активы обновлены
        self.assertEqual(self.portfolio_usdt.quantity, 1)
        self.assertEqual(self.wallet_usdt.quantity, 6)

    def test_update_dependencies_output(self):
        transaction = Transaction(type="Output",
                                  quantity=-1,
                                  wallet_id=1,
                                  portfolio_id=1,
                                  ticker_id='usdt')
        transaction.service.update_dependencies()

        # Проверяем, что активы обновлены
        self.assertEqual(self.portfolio_usdt.quantity, -1)
        self.assertEqual(self.wallet_usdt.quantity, 4)

    def test_update_dependencies_transfer_in(self):
        transaction = Transaction(type="TransferIn",
                                  quantity=1,
                                  wallet_id=1,
                                  portfolio_id=1,
                                  ticker_id='btc')
        transaction.service.update_dependencies()

        # Проверяем, что активы обновлены
        self.assertEqual(self.portfolio_btc.quantity, 11)
        self.assertEqual(self.wallet_btc.quantity, 1)

    def test_update_dependencies_transfer_out(self):
        transaction = Transaction(type="TransferOut",
                                  quantity=-1,
                                  wallet_id=1,
                                  portfolio_id=1,
                                  ticker_id='btc')
        transaction.service.update_dependencies()

        # Проверяем, что активы обновлены
        self.assertEqual(self.portfolio_btc.quantity, 9)
        self.assertEqual(self.wallet_btc.quantity, -1)

    def test_update_related_transaction_transfer_in(self):
        wallet2 = Wallet(id=2, user_id=1, name='Name')

        transaction = Transaction(type="TransferIn",
                                  date=self.date,
                                  quantity=1,
                                  wallet_id=1,
                                  ticker_id='usdt')
        transaction.wallet2_id = 2
        db.session.add_all([wallet2, transaction])
        db.session.commit()

        transaction.service.update_related_transaction()

        # Проверяем, что связанная транзакция создана
        self.assertIsNotNone(transaction.related_transaction)
        self.assertEqual(transaction.related_transaction.type, "TransferOut")
        self.assertEqual(transaction.related_transaction.quantity, 1)

    def test_update_related_transaction_transfer_out(self):
        wallet2 = Wallet(id=2, user_id=1, name='Name')

        transaction = Transaction(type="TransferOut",
                                  date=self.date,
                                  quantity=1,
                                  wallet_id=1,
                                  ticker_id='usdt')
        transaction.wallet2_id = 2
        db.session.add_all([wallet2, transaction])
        db.session.commit()

        transaction.service.update_related_transaction()

        # Проверяем, что связанная транзакция создана
        self.assertIsNotNone(transaction.related_transaction)
        self.assertEqual(transaction.related_transaction.type, "TransferIn")
        self.assertEqual(transaction.related_transaction.quantity, -1)

    def test_update_related_transaction_cancel(self):
        transaction = Transaction(id=2,
                                  type="TransferIn",
                                  quantity=1,
                                  wallet_id=1,
                                  ticker_id='usdt')
        transaction.wallet2_id = 2
        related_transaction = Transaction(id=3,
                                          type="TransferOut",
                                          quantity=-1,
                                          wallet_id=1,
                                          ticker_id='usdt')
        related_transaction.wallet2_id = 1

        transaction.related_transaction_id = 3
        related_transaction.related_transaction_id = 2

        db.session.add_all([transaction, related_transaction])
        db.session.commit()

        transaction.service.update_related_transaction(param='cancel')

        # Проверяем, что связанная транзакция удалена
        self.assertIsNone(transaction.related_transaction)
        self.assertIsNone(db.session.get(Transaction, 3))

    def test_convert_order_to_transaction(self):
        # Создаем ордер на покупку
        transaction = Transaction(id=2,
                                  type="Buy",
                                  quantity=1,
                                  quantity2=1000,
                                  price=50000,
                                  price_usd=50000,
                                  wallet_id=1,
                                  portfolio_id=1,
                                  ticker_id='btc',
                                  ticker2_id='usdt',
                                  order=True)

        self.portfolio_btc.buy_orders = 100000
        self.wallet_btc.buy_orders = 100000
        transaction.service.convert_order_to_transaction()

        # Проверяем, что ордер преобразован в транзакцию
        self.assertFalse(transaction.order)
        self.assertEqual(self.portfolio_btc.buy_orders, 50000)
        self.assertEqual(self.portfolio_usdt.sell_orders, 1000)
        self.assertEqual(self.wallet_btc.buy_orders, 50000)
        self.assertEqual(self.wallet_usdt.sell_orders, 1000)

    def test_delete_transaction(self):
        self.transaction.service.delete()

        # Проверяем, что транзакция удалена
        self.assertIsNone(db.session.get(Transaction, 1))
        self.assertEqual(self.portfolio_btc.amount, 500000)
        self.assertEqual(self.portfolio_btc.quantity, 10)
        self.assertEqual(self.portfolio_btc.buy_orders, 0)
        self.assertEqual(self.wallet_btc.quantity, 0)
        self.assertEqual(self.wallet_usdt.quantity, 5)
        self.assertEqual(self.wallet_btc.buy_orders, 0)
        self.assertEqual(self.wallet_btc.sell_orders, 0)
        self.assertEqual(self.wallet_usdt.buy_orders, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
