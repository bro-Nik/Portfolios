# from portfolio_tracker.app import app
from celery import Celery

from portfolio_tracker.app import create_app

app = create_app()
