import unittest

from portfolio_tracker.app import db
from portfolio_tracker.models import Asset, OtherAsset, Portfolio, User
from tests import app


class TestPortfolioModel(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_portfolio_edit(self):
        u = User(email='test@test', password='dog')
        db.session.add(u)

        p = Portfolio(market='crypto', name='Test')
        u.portfolios.append(p)
        db.session.commit()

        p.edit({'name': 'Test', 'percent': '10', 'comment': 'Comment'})

        self.assertEqual(p.name, 'Test2')
        self.assertEqual(p.percent, 10)
        self.assertEqual(p.comment, 'Comment')

    def test_portfolio_is_empty(self):
        u = User(email='test@test', password='dog')
        db.session.add(u)

        p = Portfolio(market='crypto', name='Test')
        u.portfolios.append(p)
        db.session.commit()

        self.assertEqual(p.is_empty(), True)

        p.comment = 'Comment'
        self.assertEqual(p.is_empty(), False)

        p.comment = ''
        p.assets = [Asset(),]
        self.assertEqual(p.is_empty(), False)

        p.assets = []
        p.other_assets = [OtherAsset(),]
        self.assertEqual(p.is_empty(), False)

    def test_portfolio_delete(self):
        u = User(email='test@test', password='dog')
        db.session.add(u)

        p = Portfolio(market='crypto')
        u.portfolios.append(p)
        db.session.commit()

        p.delete()
        db.session.commit()

        self.assertEqual(u.portfolios, [])
