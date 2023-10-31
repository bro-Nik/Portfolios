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
celery = Celery(__name__)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    # app.config.from_pyfile('settings.py')

    # db = SQLAlchemy()
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    make_celery(app)

    from portfolio_tracker.user.utils import get_locale, get_timezone
    babel.init_app(app, default_locale='ru', locale_selector=get_locale, timezone_selector=get_timezone)

    from portfolio_tracker.portfolio import bp as portfolio_bp
    app.register_blueprint(portfolio_bp, url_prefix='/portfolios')

    from portfolio_tracker.wallet.wallet import wallet
    app.register_blueprint(wallet, url_prefix='/wallets')

    from portfolio_tracker.watchlist.watchlist import watchlist
    app.register_blueprint(watchlist, url_prefix='/watchlist')

    from portfolio_tracker.admin.admin import admin
    app.register_blueprint(admin, url_prefix='/admin')

    from portfolio_tracker.user import bp as user_bp
    app.register_blueprint(user_bp, url_prefix='/user')

    from portfolio_tracker.errors import bp as errors_bp
    app.register_blueprint(errors_bp)

    from portfolio_tracker.page import bp as page_bp
    app.register_blueprint(page_bp)

    from portfolio_tracker.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from portfolio_tracker.main import bp as main_bp
    app.register_blueprint(main_bp)


    # Logging
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/portfolios.log', maxBytes=10240,
                                           backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('Portfolios startup')
    return app


def make_celery(app):
    # celery = Celery(app.name)
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery



# celery = make_celery(app)
redis = redis.StrictRedis('127.0.0.1', 6379)
# login_manager = LoginManager(app)
# login_manager.login_view = 'user.login'
# login_manager.login_message = gettext('Пожалуйста, войдите, чтобы получить доступ к этой странице')
# login_manager.login_message_category = 'danger'
# migrate = Migrate(app,  db)



# babel = Babel(app, default_locale='ru', locale_selector=get_locale, timezone_selector=get_timezone)



if __name__ == '__main__':
    app.run()
