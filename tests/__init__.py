
import unittest

from portfolio_tracker.app import create_app, db
from portfolio_tracker.settings import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SERVER_NAME = 'Dev'

    CRYPTO_PREFIX = ''
    STOCKS_PREFIX = ''
    CURRENCY_PREFIX = 'currency_'


app = create_app(TestConfig)


if __name__ == '__main__':
    unittest.main()
