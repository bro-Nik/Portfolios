from flask import Blueprint


bp = Blueprint('user', __name__, template_folder='templates')

from portfolio_tracker.user import routes, utils
