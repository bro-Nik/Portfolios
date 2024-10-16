from flask import render_template

from ..user.services.ui import get_locale
from . import bp


@bp.route('/', methods=['GET'])
def index():
    """Main page."""
    return render_template('page/index.html', locale=get_locale())
