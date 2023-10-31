from flask import Blueprint


bp = Blueprint('errors', __name__, template_folder='templates')

from portfolio_tracker.errors import handlers
