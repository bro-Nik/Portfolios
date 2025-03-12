import unittest

from flask_login import login_user

from tests import app, db
from portfolio_tracker.user.models import User
from portfolio_tracker.portfolio.models import OtherAsset, OtherBody, \
    OtherTransaction, Portfolio, Ticker


class TestPortfolioOtherAsset(unittest.TestCase):
    """Класс для тестирования методов актива"""
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Актив
        self.asset = OtherAsset(id=1, name='Name', portfolio_id=1)
        db.session.add(self.asset)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_is_empty(self):
        self.assertEqual(self.asset.is_empty, True)

    def test_not_empty_with_comment(self):
        self.asset.comment = 'Comment'
        self.assertEqual(self.asset.is_empty, False)

    def test_not_empty_with_transaction(self):
        tranasction = OtherTransaction(amount_ticker_id='', type='')
        self.asset.transactions = [tranasction]

        self.assertEqual(self.asset.is_empty, False)


class TestPortfolioOtherAssetService(unittest.TestCase):
    """Класс для тестирования методов офлайн актива"""

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.user = User(email='test@test', password='dog')
        db.session.add(self.user)

        # Тикеры
        self.usdt = Ticker(id='usdt', name='USDT', price=0.9, symbol='Tether', market='crypto')
        db.session.add(self.usdt)

        # Портфель
        self.portfolio = Portfolio(id=1, user_id=1, market='crypto', name='Test Portfolio')
        self.user.portfolios.append(self.portfolio)

        # Актив портфеля
        self.asset = OtherAsset(id=1, portfolio_id=1, name='Name')
        db.session.add(self.asset)

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit_empty_form(self):
        form = {}
        self.asset.service.edit(form)

        self.assertEqual(self.asset.name, 'Name')
        self.assertEqual(self.asset.percent, 0)
        self.assertEqual(self.asset.comment, '')

    def test_edit(self):
        form = {'name': 'Name', 'comment': 'New Comment', 'percent': 50}
        self.asset.service.edit(form)

        self.assertEqual(self.asset.name, 'Name2')
        self.assertEqual(self.asset.percent, 50)
        self.assertEqual(self.asset.comment, 'New Comment')

    def test_get_transaction(self):
        transaction1 = OtherTransaction(id=1)
        transaction2 = OtherTransaction(id=2)
        transaction3 = OtherTransaction(id=3)
        self.asset.transactions = [transaction1, transaction2, transaction3]

        self.assertEqual(self.asset.service.get_transaction(1), transaction1)
        self.assertEqual(self.asset.service.get_transaction(2), transaction2)
        self.assertEqual(self.asset.service.get_transaction(3), transaction3)
        self.assertEqual(self.asset.service.get_transaction(5), None)

    def test_create_transaction(self):
        transaction = self.asset.service.create_transaction()

        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.type, 'Profit')
        self.assertEqual(transaction.amount, 0)

    def test_get_body(self):
        body1 = OtherBody(id=1)
        body2 = OtherBody(id=2)
        body3 = OtherBody(id=3)
        self.asset.bodies = [body1, body2, body3]

        self.assertEqual(self.asset.service.get_body(1), body1)
        self.assertEqual(self.asset.service.get_body(2), body2)
        self.assertEqual(self.asset.service.get_body(3), body3)
        self.assertEqual(self.asset.service.get_body(5), None)

    def test_create_body(self):
        body = self.asset.service.create_body()

        self.assertIsNotNone(body)

    def test_delete_if_empty(self):
        with app.test_request_context():
            login_user(self.user, False)
            self.asset.service.delete_if_empty()

            # Проверяем, что актив удален
            self.assertIsNone(db.session.get(OtherAsset, 1))

    def test_do_not_delete_if_not_empty(self):
        # Добавим комментарий
        self.asset.comment = 'Comment'
        db.session.commit()

        with app.test_request_context():
            login_user(self.user, False)
            self.asset.service.delete_if_empty()

            # Проверяем, что актив не удален
            self.assertIsNotNone(db.session.get(OtherAsset, 1))

    def test_delete(self):
        other = {'amount_ticker_id': '', 'type': ''}
        tranasction1 = OtherTransaction(asset_id=1, **other)
        tranasction2 = OtherTransaction(asset_id=1, **other)
        tranasction3 = OtherTransaction(asset_id=1, **other)
        self.asset.transactions = [tranasction1, tranasction2, tranasction3]

        other = {'name': '', 'amount_ticker_id': '', 'cost_now_ticker_id': ''}
        body1 = OtherBody(id=1, **other)
        body2 = OtherBody(id=2, **other)
        body3 = OtherBody(id=3, **other)
        self.asset.bodies = [body1, body2, body3]

        db.session.commit()

        # Удаление транзакций, тел актива и актива
        self.asset.service.delete()
        db.session.commit()

        self.assertEqual(self.asset.transactions, [])
        self.assertEqual(self.asset.bodies, [])
        self.assertEqual(self.portfolio.other_assets, [])

        self.assertIsNone(db.session.get(OtherAsset, 1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
