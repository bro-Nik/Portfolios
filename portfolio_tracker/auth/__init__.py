from flask import Blueprint


bp = Blueprint('auth', __name__, template_folder='templates')


from ..app import db, login_manager
from ..models import User, UserInfo
from . import routes
