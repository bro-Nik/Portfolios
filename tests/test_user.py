import unittest
from unittest.mock import patch

from flask_login import login_user
from werkzeug.security import check_password_hash, generate_password_hash
from flask import request

from portfolio_tracker.portfolio.models import Asset, OtherAsset, OtherBody, \
    OtherTransaction, Portfolio, Transaction
from portfolio_tracker.wallet.models import Wallet, WalletAsset
from portfolio_tracker.watchlist.models import Alert, WatchlistAsset
from portfolio_tracker.user.models import User, UserInfo
from tests import app, db


class TestUser(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Создаем тестовые данные
        self.user = User(id=1, email='test@example.com', type='')

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_is_demo(self):
        self.user.type = 'demo'
        self.assertTrue(self.user.is_demo)

    def test_is_not_demo(self):
        self.assertFalse(self.user.is_demo)

class TestUserService(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Создаем тестовые данные
        self.user = User(id=1, email='test@example.com', info=UserInfo())
        self.user.service.set_password('password123')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_set_password(self):
        password = 'password123'
        self.user.service.set_password(password)
        self.assertTrue(check_password_hash(self.user.password, password))

    def test_check_password(self):
        password = 'password123'
        self.user.password = generate_password_hash(password)
        self.assertTrue(self.user.service.check_password(password))
        self.assertFalse(self.user.service.check_password('wrongpassword'))

    @patch('portfolio_tracker.user.repository.UserRepository.delete')
    @patch('portfolio_tracker.user.services.user.UserService.cleare_data')
    def test_delete(self, mock_cleare_data, mock_delete):
        self.user.service.delete()

        mock_delete.assert_called_once_with(self.user)
        mock_cleare_data.assert_called_once()

    @patch('portfolio_tracker.watchlist.repository.AlertRepository.delete')
    @patch('portfolio_tracker.watchlist.repository.AssetRepository.delete')
    def test_cleare_data_in_watchlist(self, mock_asset_delete, mock_alert_delete) -> None:
        alert = Alert(price=0, price_usd=0, price_ticker_id='', type='', comment='')
        asset = WatchlistAsset(ticker_id='', comment='', alerts=[alert])
        self.user.watchlist = [asset]
        self.user.service.cleare_data()

        mock_asset_delete.assert_called_once_with(asset)
        mock_alert_delete.assert_called_once_with(alert)

    @patch('portfolio_tracker.wallet.repository.WalletAssetRepository.delete')
    @patch('portfolio_tracker.wallet.repository.WalletRepository.delete')
    def test_cleare_data_in_wallets(self, mock_wallet_delete, mock_asset_delete) -> None:
        asset = WalletAsset(ticker_id='')
        wallet = Wallet(name='', assets=[asset])
        self.user.wallets = [wallet]
        db.session.commit()
        self.user.service.cleare_data()

        mock_asset_delete.assert_called_once_with(asset)
        mock_wallet_delete.assert_called_once_with(wallet)

    @patch('portfolio_tracker.portfolio.repository.TransactionRepository.delete')
    @patch('portfolio_tracker.portfolio.repository.AssetRepository.delete')
    @patch('portfolio_tracker.portfolio.repository.PortfolioRepository.delete')
    def test_cleare_data_in_portfolios(self, mock_portfolio_delete, mock_asset_delete, mock_transaction_delete) -> None:
        transaction = Transaction(quantity=0, type='', wallet_id=0, portfolio_id=1)
        asset = Asset(id=1, ticker_id='', transactions=[transaction], portfolio_id=1)
        portfolio = Portfolio(id=1, name='', market='', assets=[asset])
        self.user.portfolios = [portfolio]
        db.session.commit()
        self.user.service.cleare_data()

        mock_transaction_delete.assert_called_once_with(transaction)
        mock_asset_delete.assert_called_once_with(asset)
        mock_portfolio_delete.assert_called_once_with(portfolio)

    @patch('portfolio_tracker.portfolio.repository.BodyRepository.delete')
    @patch('portfolio_tracker.portfolio.repository.OtherTransactionRepository.delete')
    @patch('portfolio_tracker.portfolio.repository.OtherAssetRepository.delete')
    @patch('portfolio_tracker.portfolio.repository.PortfolioRepository.delete')
    def test_cleare_data_in_other_portfolios(self, mock_portfolio_delete, mock_asset_delete, mock_transaction_delete, mock_body_delete) -> None:
        body = OtherBody(name='', amount_ticker_id='', cost_now_ticker_id='')
        transaction = OtherTransaction(amount_ticker_id='', type='')
        asset = OtherAsset(transactions=[transaction], bodies=[body])
        portfolio = Portfolio(id=1, name='', market='', other_assets=[asset])
        self.user.portfolios = [portfolio]
        db.session.commit()
        self.user.service.cleare_data()

        mock_body_delete.assert_called_once_with(body)
        mock_transaction_delete.assert_called_once_with(transaction)
        mock_asset_delete.assert_called_once_with(asset)
        mock_portfolio_delete.assert_called_once_with(portfolio)

    def test_change_currency(self):
        self.user.service.change_currency()
        self.assertEqual(self.user.currency, 'usd')
        self.assertEqual(self.user.currency_ticker_id, 'currency_usd')

        self.user.service.change_currency('eur')
        self.assertEqual(self.user.currency, 'eur')
        self.assertEqual(self.user.currency_ticker_id, 'currency_eur')

    def test_change_locale(self):
        self.user.service.change_locale()
        self.assertEqual(self.user.locale, 'en')

        self.user.service.change_locale('ru')
        self.assertEqual(self.user.locale, 'ru')

    @patch('portfolio_tracker.user.services.user.requests.get')
    @patch('portfolio_tracker.user.services.user.UserRepository.save')
    def test_new_login_with_ip(self, mock_save, mock_get):
        mock_get.return_value.json.return_value = {
            'status': 'success',
            'country': 'Russia',
            'city': 'Moscow'
        }
        with app.test_request_context():
            request.headers = {'X-Real-IP': '127.0.0.1'}

            self.user.service.new_login()
            self.assertEqual(self.user.info.country, 'Russia')
            self.assertEqual(self.user.info.city, 'Moscow')
            mock_save.assert_called_once_with(self.user)

    @patch('portfolio_tracker.user.services.user.requests.get')
    @patch('portfolio_tracker.user.services.user.UserRepository.save')
    def test_new_login_without_ip(self, mock_save, mock_get):
        with app.test_request_context():
            request.headers = {}

            self.user.service.new_login()
            mock_get.assert_not_called()
            mock_save.assert_not_called()

    def test_make_admin(self):
        self.user.service.make_admin()
        self.assertEqual(self.user.type, 'admin')

    def test_unmake_admin(self):
        self.user.type = 'admin'
        self.user.service.unmake_admin()
        self.assertEqual(self.user.type, '')

    def test_recalculate(self):
        # ToDo
        pass

    def test_create_portfolio(self):
        portfolio = self.user.service.create_portfolio()
        self.assertIsNotNone(portfolio)
        self.assertEqual(portfolio.user_id, 1)

    def test_get_portfolio(self):
        portfolio = Portfolio(id=1)
        self.user.portfolios = [portfolio]
        result = self.user.service.get_portfolio(1)
        self.assertEqual(result, portfolio)

    def test_create_wallet(self):
        wallet = self.user.service.create_wallet()
        self.assertIsNotNone(wallet)
        self.assertEqual(wallet.user_id, 1)

    def test_create_default_wallet(self):
        with app.test_request_context():
            login_user(self.user, False)

            self.user.service.create_default_wallet()
            self.assertEqual(len(self.user.wallets), 1)

    def test_get_wallet(self):
        wallet = Wallet(id=1)
        self.user.wallets = [wallet]
        result = self.user.service.get_wallet(1)
        self.assertEqual(result, wallet)

    def test_get_watchlist(self):
        watchlist = self.user.service.get_watchlist()
        self.assertEqual(watchlist.assets, self.user.watchlist)


if __name__ == '__main__':
    unittest.main(verbosity=2)
