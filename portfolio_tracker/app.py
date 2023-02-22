from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from celery import Celery
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

from portfolio_tracker.admin import start_update_prices

with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run()
