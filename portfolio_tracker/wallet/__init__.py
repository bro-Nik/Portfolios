from flask import Blueprint


bp = Blueprint('wallet', __name__, template_folder='templates')

from . import routes
