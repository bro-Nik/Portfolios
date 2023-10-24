import os
from dotenv import load_dotenv, find_dotenv

basedir = os.path.abspath(os.path.dirname(__name__))
load_dotenv(os.path.join(basedir, '.env'))
load_dotenv(find_dotenv())


SECRET_KEY = os.environ.get('SECRET_KEY')
SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI')
FLASK_DEBUG = os.environ.get('FLASK_DEBUG')

API_KEY_POLYGON = os.environ.get('API_KEY_POLYGON')
API_KEY_CURRENCYLAYER = os.environ.get('API_KEY_CURRENCYLAYER')

CRYPTO_UPDATE = os.environ.get('CRYPTO_UPDATE')
STOCKS_UPDATE = os.environ.get('STOCKS_UPDATE')

UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER')
ALLOWED_EXTENSIONS = os.environ.get('ALLOWED_EXTENSIONS')

BABEL_TRANSLATION_DIRECTORIES = os.environ.get('BABEL_TRANSLATION_DIRECTORIES')

CRYPTO_PREFIX = os.environ.get('CRYPTO_PREFIX')
STOCKS_PREFIX = os.environ.get('STOCKS_PREFIX')
CURRENCY_PREFIX = os.environ.get('CURRENCY_PREFIX')
