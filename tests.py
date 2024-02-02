import unittest

from portfolio_tracker.app import create_app, db
from portfolio_tracker.settings import Config
from portfolio_tracker.portfolio.models import *
from portfolio_tracker.user.models import *


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SERVER_NAME = 'Dev'


app = create_app(TestConfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
