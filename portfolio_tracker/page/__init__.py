from flask import Blueprint


bp = Blueprint('page', __name__, template_folder='templates')

from . import routes
