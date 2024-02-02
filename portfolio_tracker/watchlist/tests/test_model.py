import unittest

from tests import app, db, User, Ticker
from ..models import Alert, WatchlistAsset


class TestWatchlistAssetModel(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.user = User(email='test@test', password='dog')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit(self):
        asset = WatchlistAsset(ticker_id='btc')
        asset.edit({'comment': 'Comment'})

        self.assertEqual(asset.comment, 'Comment')

    def test_is_empty(self):
        asset1 = WatchlistAsset(ticker_id='btc')
        asset2 = WatchlistAsset(ticker_id='eth', comment='Comment')
        asset3 = WatchlistAsset(ticker_id='aapl', alerts=[Alert()])

        self.assertEqual(asset1.is_empty(), True)
        self.assertEqual(asset2.is_empty(), False)
        self.assertEqual(asset3.is_empty(), False)

    def test_delete_if_empty(self):
        asset1 = WatchlistAsset(ticker_id='btc', alerts=[Alert()])
        asset2 = WatchlistAsset(ticker_id='eth', alerts=[Alert(transaction_id=1)])
        asset3 = WatchlistAsset(ticker_id='ltc', comment='Comment')
        self.user.watchlist = [asset1, asset2, asset3]
        db.session.commit()

        asset1.delete_if_empty()
        asset2.delete_if_empty()
        asset3.delete_if_empty()
        db.session.commit()

        self.assertEqual(self.user.watchlist, [asset2, asset3])

    def test_delete(self):
        asset1 = WatchlistAsset(ticker_id='btc', alerts=[Alert()])
        asset2 = WatchlistAsset(ticker_id='eth', alerts=[Alert(transaction_id=1)])
        asset3 = WatchlistAsset(ticker_id='ltc', comment='Comment')
        self.user.watchlist = [asset1, asset2, asset3]
        db.session.commit()

        asset1.delete()
        asset2.delete()
        asset3.delete()
        db.session.commit()

        self.assertEqual(self.user.watchlist, [])


class TestAlertModel(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.user = User(email='test@test', password='dog')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_edit(self):
        # Тикер
        usd = Ticker(id='usd', price=1)
        usdt = Ticker(id='usdt', price=0.98)
        alert = Alert()
        asset = WatchlistAsset(ticker_id='usdt', alerts=[alert])
        db.session.add_all([usd, usdt, asset])
        db.session.commit()

        alert.edit({'price': 10, 'price_ticker_id': 'usd', 'comment': 'Comment'})

        self.assertEqual(alert.price, 10)
        self.assertEqual(alert.price_usd, 10 / 1)
        self.assertEqual(alert.price_ticker_id, 'usd')
        self.assertEqual(alert.comment, 'Comment')

    def test_turn_off(self):
        alert1 = Alert(status='on')
        alert2 = Alert(status='on', transaction_id=1)

        alert1.turn_off()
        alert2.turn_off()

        self.assertEqual(alert1.status, 'off')
        self.assertEqual(alert2.status, 'on')

    def test_turn_on(self):
        alert1 = Alert(status='off')
        alert2 = Alert(status='off', transaction_id=2, asset_id=2)

        alert1.turn_on()
        alert2.turn_on()

        self.assertEqual(alert1.status, 'on')
        self.assertEqual(alert2.status, 'on')
        self.assertEqual(alert2.transaction_id, None)
        self.assertEqual(alert2.asset_id, None)

    def test_delete(self):
        alert1 = Alert(status='off')
        alert2 = Alert(status='off', transaction_id=2)
        asset = WatchlistAsset(alerts=[alert1, alert2])
        db.session.add(asset)
        db.session.commit()

        alert1.delete()
        alert2.delete()
        db.session.commit()

        self.assertEqual(asset.alerts, [alert2])
