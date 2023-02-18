from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from celery import Celery
from flask_admin import Admin
import redis
import pymysql

def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('settings.py')

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

from portfolio_tracker.defs import *

#with app.app_context():
#    price_list_crypto_def.delay()
#    price_list_stocks_def.delay()


if __name__ == '__main__':
    app.run()