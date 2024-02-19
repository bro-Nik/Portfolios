import os
import coverage
import unittest

from portfolio_tracker.app import create_app, db
from portfolio_tracker.settings import Config
from portfolio_tracker.portfolio.models import *
from portfolio_tracker.wallet.models import *
from portfolio_tracker.watchlist.models import *
from portfolio_tracker.user.models import *
from portfolio_tracker.admin.models import *


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SERVER_NAME = 'Dev'

    CRYPTO_PREFIX = ''
    STOCKS_PREFIX = ''
    CURRENCY_PREFIX = ''


app = create_app(TestConfig)


if __name__ == '__main__':
    unittest.main()
    # unittest.main(verbosity=2)
