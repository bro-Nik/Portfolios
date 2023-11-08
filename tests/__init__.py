import unittest

from portfolio_tracker.app import create_app
from portfolio_tracker.settings import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'


app = create_app(TestConfig)


# if __name__ == '__main__':
#     unittest.main(verbosity=2)
