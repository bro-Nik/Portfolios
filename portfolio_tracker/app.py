from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from celery import Celery
import redis

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

redis = redis.StrictRedis('localhost', 6379)

login_manager = LoginManager(app)

from portfolio_tracker.models import Setting, Market
from portfolio_tracker.defs import *

with app.app_context():
    global settings_list
    try:
        settings = db.session.execute(db.select(Setting)).scalar()
        if settings:
            # не первый запуск
            markets_in_base = db.session.execute(db.select(Market)).scalars()
            settings_in_base = tuple(db.session.execute(db.select(Setting)).scalars())
            if markets_in_base != ():
                settings_list['markets'] = {}
                settings_list['update_period'] = {}
                for market in markets_in_base:
                    settings_list['markets'][market.id] = market.name

                    if market.id == 'crypto':
                        for item in settings_in_base:
                            if item.name == market.id:
                                settings_list['update_period'][market.id] = int(item.value)

                    if market.id == 'stocks':
                        for item in settings_in_base:
                            if item.name == market.id:
                                settings_list['update_period'][market.id] = int(item.value)
                            if item.name == 'api_key_polygon':
                                settings_list['api_key_polygon'] = item.value
            price_list_def()

        else:
            settings_list['first_start'] = True
    except:
        # первый запуск
        with app.app_context():
            db.create_all()

if __name__ == '__main__':
    app.run()