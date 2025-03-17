import os
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask
from flask_babel import Babel, gettext
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from celery import Celery
from redis import Redis

from portfolio_tracker.models import Base

from .settings import Config


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'user.login'
login_manager.login_message = gettext(
    'Пожалуйста, войдите, чтобы получить доступ к этой странице')
login_manager.login_message_category = 'danger'
babel = Babel()
celery = Celery('celery_app', broker='amqp://rabbitmq')
redis = Redis()


from .user.services.ui import get_locale, get_timezone
from .errors.handlers import init_request_errors


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    init_celery(app)
    init_redis(app)

    babel.init_app(app, locale_selector=get_locale, timezone_selector=get_timezone)

    register_blueprints(app)

    configure_logging(app)
    init_request_errors(app)

    return app

def init_redis(app):
    redis.__init__(
        host=app.config.get('REDIS_HOST', 'redis'),
        port=app.config.get('REDIS_PORT', 6379),
        # decode_responses=True
    )


def register_blueprints(app):
    from .portfolio import bp as portfolio_bp
    app.register_blueprint(portfolio_bp, url_prefix='/portfolios')

    from .wallet import bp as wallet_bp
    app.register_blueprint(wallet_bp, url_prefix='/wallets')

    from .watchlist import bp as watchlist_bp
    app.register_blueprint(watchlist_bp, url_prefix='/watchlist')

    from .admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from .user import bp as user_bp
    app.register_blueprint(user_bp, url_prefix='/user')

    from .page import bp as page_bp
    app.register_blueprint(page_bp)

    from .api import bp as api_bp
    app.register_blueprint(api_bp)

    from .jinja_filters import bp as jf_bp
    app.register_blueprint(jf_bp)

    from .errors import bp as errors_bp
    app.register_blueprint(errors_bp)


def configure_logging(app):
    if app.testing:
        app.logger.setLevel(logging.CRITICAL)

        #NEW
        # logging.basicConfig()
        # logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
        return

    if not os.path.exists('logs'):
        os.mkdir('logs')

    # формат логов
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')

    app.logger.setLevel(logging.INFO)

    # обработчик уровня Info
    file_handler_info = RotatingFileHandler('logs/portfolios_info.log',
                                            maxBytes=10240, backupCount=10)
    file_handler_info.setFormatter(formatter)
    file_handler_info.setLevel(logging.INFO)
    app.logger.addHandler(file_handler_info)

    # обработчик уровня Warning
    file_handler_warning = RotatingFileHandler('logs/portfolios_warning.log',
                                               maxBytes=10240, backupCount=10)
    file_handler_warning.setFormatter(formatter)
    file_handler_warning.setLevel(logging.WARNING)
    app.logger.addHandler(file_handler_warning)

    # обработчик уровня Error
    file_handler_error = RotatingFileHandler('logs/portfolios_error.log',
                                             maxBytes=10240, backupCount=10)
    file_handler_error.setFormatter(formatter)
    file_handler_error.setLevel(logging.ERROR)
    app.logger.addHandler(file_handler_error)

    app.logger.info('Portfolios startup')


def init_celery(app):
    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask

    celery.autodiscover_tasks()
    return celery
