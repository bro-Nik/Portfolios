from flask import render_template

from portfolio_tracker.page import bp
from portfolio_tracker.user.utils import get_locale


@bp.route('/', methods=['GET'])
def index():
    """Main page."""
    return render_template('page/index.html', locale=get_locale())
