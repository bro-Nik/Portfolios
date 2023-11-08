from flask import Blueprint


bp = Blueprint('watchlist', __name__, template_folder='templates')

from portfolio_tracker.watchlist import routes, utils
