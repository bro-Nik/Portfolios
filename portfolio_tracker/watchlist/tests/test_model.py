import unittest

from portfolio_tracker.app import db
from portfolio_tracker.models import Alert, User, WatchlistAsset
from tests import app


class TestWatchlistModel(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_watchlist_asset_edit(self):
        u = User(email='test@test', password='dog')
        db.session.add(u)

        a1 = WatchlistAsset(ticker_id='btc')
        u.watchlist.append(a1)
        db.session.commit()
        a1.edit({'comment': 'Comment'})

        self.assertEqual(a1.comment, 'Comment')

    def test_watchlist_asset_is_empty(self):
        u = User(email='test@test', password='dog')
        db.session.add(u)

        a = WatchlistAsset()
        u.watchlist.append(a)
        db.session.commit()

        self.assertEqual(a.is_empty(), True)

        a.comment = 'Comment'
        self.assertEqual(a.is_empty(), False)

        a.comment = ''
        a.alerts = [Alert(),]
        self.assertEqual(a.is_empty(), False)

    def test_watchlist_asset_delete(self):
        u = User(email='test@test', password='dog')
        db.session.add(u)

        a = WatchlistAsset()
        u.watchlist.append(a)
        db.session.commit()

        a.delete()
        db.session.commit()

        self.assertEqual(u.watchlist, [])

class TestAlertModel(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_alert_edit(self):
        u = User(email='test@test', password='dog')
        db.session.add(u)

        alert = Alert()
        asset = WatchlistAsset(alerts=[alert,])
        u.watchlist.append(asset)
        db.session.commit()

        alert.edit({'price': 10, 'price_ticker_id': 'usd', 'comment': 'Comment'})

        self.assertEqual(alert.price, 10)
        self.assertEqual(alert.price_usd, 10 / 1)
        self.assertEqual(alert.price_ticker_id, 'usdt')
        self.assertEqual(alert.comment, 'Comment')

    def test_alert_turn_off(self):
        u = User(email='test@test', password='dog')
        db.session.add(u)

        alert = Alert(status='on')
        asset = WatchlistAsset(alerts=[alert,])
        u.watchlist.append(asset)
        db.session.commit()

        alert.turn_off()

        self.assertEqual(alert.status, 'off')

    def test_alert_turn_on(self):
        u = User(email='test@test', password='dog')
        db.session.add(u)

        alert = Alert(status='off')
        asset = WatchlistAsset(alerts=[alert,])
        u.watchlist.append(asset)
        db.session.commit()

        alert.turn_on()

        self.assertEqual(alert.status, 'on')

    def test_alert_delete(self):
        u = User(email='test@test', password='dog')
        db.session.add(u)

        alert = Alert(status='off')
        asset = WatchlistAsset(alerts=[alert,])
        u.watchlist.append(asset)
        db.session.commit()

        alert.delete()

        self.assertEqual(asset.alerts, [])
