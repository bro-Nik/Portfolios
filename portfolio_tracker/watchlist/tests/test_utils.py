import unittest

from flask_login import login_user

from tests import app, db, User, Ticker
from ..models import Alert, WatchlistAsset
from ..utils import create_new_alert, create_new_asset, get_alert, get_asset


class TestWatchlistUtils(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Пользователь
        self.user = User(id=1, email='test@test', password='dog')
        db.session.add(self.user)
        db.session.commit()

        # Login
        with self.app.test_request_context():
            login_user(self.user)

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_asset(self):
        a1 = WatchlistAsset(id=1, ticker_id='btc')
        a2 = WatchlistAsset(id=2, ticker_id='eth')
        a3 = WatchlistAsset(id=3, ticker_id='usdt')
        self.user.watchlist = [a1, a2, a3]
        db.session.commit()

        with self.app.test_request_context():
            self.assertEqual(get_asset('1'), a1)
            self.assertEqual(get_asset(None, 'eth'), a2)
            self.assertEqual(get_asset(3), a3)
            self.assertEqual(get_asset(4), None)
            self.assertEqual(get_asset(None), None)

    def test_get_alert(self):
        a = WatchlistAsset(id=1, ticker_id='btc')
        self.user.watchlist = [a]
        alert1 = Alert(id=1)
        alert2 = Alert(id=2)
        a.alerts = [alert1, alert2]
        db.session.commit()

        self.assertEqual(get_alert(1, a), alert1)
        self.assertEqual(get_alert('1', a), alert1)
        self.assertEqual(get_alert('2', a), alert2)
        self.assertEqual(get_alert(2, a), alert2)
        self.assertEqual(get_alert(2, None), None)
        self.assertEqual(get_alert(3, a), None)
        self.assertEqual(get_alert(None, a), None)

    def test_create_new_asset(self):
        # Тикеры
        t = Ticker(id='btc')
        db.session.add(t)
        db.session.commit()

        with self.app.test_request_context():
            a = create_new_asset(t)
            db.session.commit()

            self.assertEqual(len(self.user.watchlist), 1)
            self.assertEqual(a.ticker_id, 'btc')

    def test_create_new_alert(self):
        a = WatchlistAsset(id=1, ticker_id='btc')
        self.user.watchlist = [a]
        db.session.commit()

        create_new_alert(a)
        self.assertEqual(len(a.alerts), 1)
