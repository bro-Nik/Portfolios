from flask import Blueprint


bp = Blueprint('portfolio', __name__, template_folder='templates')

from portfolio_tracker.portfolio import routes, utils
