import os
from dotenv import load_dotenv, find_dotenv


basedir = os.path.abspath(os.path.dirname(__name__))
load_dotenv(os.path.join(basedir, '.env'))
load_dotenv(find_dotenv())


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'some secret key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI')
    FLASK_DEBUG = os.environ.get('FLASK_DEBUG')
    FLASK_RUN_PORT = os.environ.get('FLASK_RUN_PORT')

    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER')
    ALLOWED_EXTENSIONS = os.environ.get('ALLOWED_EXTENSIONS')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 1024))

    BABEL_TRANSLATION_DIRECTORIES = os.environ.get('BABEL_TRANSLATION_DIRECTORIES')

    # Celery
    # CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL')
    # RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND')
    # CELERY_VISIBILITY_TIMEOUT = 12000

    # Prefix
    CRYPTO_PREFIX = os.environ.get('CRYPTO_PREFIX', '')
    STOCKS_PREFIX = os.environ.get('STOCKS_PREFIX', '')
    CURRENCY_PREFIX = os.environ.get('CURRENCY_PREFIX', '')

    # API
    PROXIES_API_KEY = os.environ.get('PROXIES_API_KEY', '')


LANGUAGES = {
    'ru': 'Русский',
    'en': 'English',
    # 'de': 'Deutsch'
}
