import os
from dotenv import load_dotenv, find_dotenv

basedir = os.path.abspath(os.path.dirname(__name__))
load_dotenv(os.path.join(basedir, '.env'))
load_dotenv(find_dotenv())


SECRET_KEY = os.environ.get('SECRET_KEY')
SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI')
FLASK_DEBUG = os.environ.get('FLASK_DEBUG')

API_KEY_POLYGON = os.environ.get('API_KEY_POLYGON')

CRYPTO_UPDATE = os.environ.get('CRYPTO_UPDATE')
STOCKS_UPDATE = os.environ.get('STOCKS_UPDATE')
