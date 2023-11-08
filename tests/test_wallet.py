import unittest

from portfolio_tracker.app import db
from portfolio_tracker.models import Transaction, User, Wallet
from tests import app


class TestWalletModel(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.u = User(email='test@test', password='dog')
        db.session.add(self.u)

        self.w = Wallet(id=1, name='Test')

        self.u.wallets = [self.w,]
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_wallet_edit(self):
        self.w.edit({'name': 'Test', 'comment': 'Comment'})
        self.assertEqual(self.w.name, 'Test2')
        self.assertEqual(self.w.comment, 'Comment')

    def test_wallet_is_empty(self):
        self.assertEqual(self.w.is_empty(), True)

        self.w.comment = 'Comment'
        self.assertEqual(self.w.is_empty(), False)

        self.w.comment = ''
        self.w.transactions = [Transaction(),]
        self.assertEqual(self.w.is_empty(), False)

    def test_wallet_update_price(self):
        # to do it
        pass

    def test_wallet_delete(self):
        self.w.delete()
        self.assertEqual(self.u.wallets, [])
