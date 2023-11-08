from flask import Blueprint


bp = Blueprint('admin', __name__, template_folder='templates')

from portfolio_tracker.admin import routes, utils, tasks
