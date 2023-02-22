from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy

#  flask --app portfolio_tracker/first_start run
# go to /first_start
def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('settings.py')

    db = SQLAlchemy()
    db.init_app(app)
    return app, db

app, db = create_app()

from portfolio_tracker.models import Market, User
from portfolio_tracker.defs import *

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run()
