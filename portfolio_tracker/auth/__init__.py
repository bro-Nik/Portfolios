from flask import Blueprint


bp = Blueprint('auth', __name__, template_folder='templates')

from portfolio_tracker.auth import routes
