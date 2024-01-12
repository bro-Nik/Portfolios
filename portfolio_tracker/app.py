from flask import Flask, current_app
from flask_babel import Babel, gettext
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from celery import Celery
import redis
import logging
from logging.handlers import RotatingFileHandler
import os

from portfolio_tracker.settings import Config


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'user.login'
login_manager.login_message = gettext('Пожалуйста, войдите, чтобы получить доступ к этой странице')
login_manager.login_message_category = 'danger'
babel = Babel()
celery = Celery()
redis = redis.StrictRedis('127.0.0.1', 6379)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    # app.config.from_pyfile('settings.py')

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    init_celery(app, celery)

    from portfolio_tracker.user.utils import get_locale, get_timezone
    babel.init_app(app, default_locale='ru',
                   locale_selector=get_locale, timezone_selector=get_timezone)

    register_blueprints(app)

    configure_logging(app)

    return app


def register_blueprints(app):
    from portfolio_tracker.portfolio import bp as portfolio_bp
    app.register_blueprint(portfolio_bp, url_prefix='/portfolios')

    from portfolio_tracker.wallet import bp as wallet_bp
    app.register_blueprint(wallet_bp, url_prefix='/wallets')

    from portfolio_tracker.watchlist import bp as watchlist_bp
    app.register_blueprint(watchlist_bp, url_prefix='/watchlist')

    from portfolio_tracker.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from portfolio_tracker.user import bp as user_bp
    app.register_blueprint(user_bp, url_prefix='/user')

    from portfolio_tracker.errors import bp as errors_bp
    app.register_blueprint(errors_bp)

    from portfolio_tracker.page import bp as page_bp
    app.register_blueprint(page_bp)

    from portfolio_tracker.api import bp as api_bp
    app.register_blueprint(api_bp)

    from portfolio_tracker.jinja_filters import bp as jf_bp
    app.register_blueprint(jf_bp)


def configure_logging(app):
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/portfolios.log',
                                           maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('Portfolios startup')


def init_celery(app, celery):
    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask

    celery.autodiscover_tasks()
