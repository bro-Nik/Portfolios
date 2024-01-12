from flask import Blueprint


bp = Blueprint('portfolio', __name__, template_folder='templates')

from . import routes
