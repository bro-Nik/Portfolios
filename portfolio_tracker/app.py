from flask import Flask
from flask_babel import Babel
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from celery import Celery
import redis


def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('settings.py')

    # db = SQLAlchemy(session_options={'autoflush': False, 'autocommit': False})
    db = SQLAlchemy()
    db.init_app(app)

    return app, db


app, db = create_app()


def make_celery(app):
    celery = Celery(app.name)
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


celery = make_celery(app)
redis = redis.StrictRedis('127.0.0.1', 6379)
login_manager = LoginManager(app)
migrate = Migrate(app,  db)


from portfolio_tracker.portfolio.portfolio import portfolio
app.register_blueprint(portfolio, url_prefix='/portfolios')
from portfolio_tracker.wallet.wallet import wallet
app.register_blueprint(wallet, url_prefix='/wallets')
from portfolio_tracker.watchlist.watchlist import watchlist
app.register_blueprint(watchlist, url_prefix='/watchlist')
from portfolio_tracker.admin.admin import admin
app.register_blueprint(admin, url_prefix='/admin')
from portfolio_tracker.user.user import user, get_locale, get_timezone
app.register_blueprint(user, url_prefix='/user')

babel = Babel(app, default_locale='ru', locale_selector=get_locale, timezone_selector=get_timezone)

# with app.app_context():
#     db.create_all()


if __name__ == '__main__':
    app.run()
