import unittest

from portfolio_tracker.user.models import User
from tests import app, db
from ..models import Alert, WatchlistAsset
from ..utils import create_new_alert, create_new_watchlist_asset, get_alert, \
    get_watchlist_asset


class TestWatchlistUtils(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        u = User(email='test@test', password='dog')
        db.session.add(u)

        self.u = u
        self.a1 = WatchlistAsset(ticker_id='btc')
        self.a2 = WatchlistAsset(ticker_id='eth')
        self.a3 = WatchlistAsset(ticker_id='usdt')

        u.watchlist = [self.a1, self.a2, self.a3]
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_watchlist_asset(self):
        self.assertEqual(get_watchlist_asset('btc', user=self.u), self.a1)
        self.assertEqual(get_watchlist_asset('eth', user=self.u), self.a2)

        a4 = get_watchlist_asset('xrp', create=True, user=self.u)
        self.assertEqual(a4.ticker_id, 'xrp')

    def test_create_new_watchlist_asset(self):
        a = create_new_watchlist_asset('btc', self.u)
        self.assertEqual(len(self.u.watchlist), 4)
        self.assertEqual(a.ticker_id, 'btc')

    def test_get_alert(self):
        a = Alert(id=1)
        self.a1.alerts.append(a)

        self.assertEqual(get_alert(self.a1, 1), a)
        self.assertEqual(get_alert(self.a1, 2), None)

    def test_create_new_alert(self):
        create_new_alert(self.a1)
        self.assertEqual(len(self.a1.alerts), 1)
