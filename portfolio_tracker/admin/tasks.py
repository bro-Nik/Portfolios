from portfolio_tracker.admin.utils import task_logging
from ..app import celery
from .utils import api_logging
from . import currency, stocks, crypto, proxy


@celery.task(bind=True, name='api_logging_clear', max_retries=None)
@task_logging
def api_logging_clear(self) -> None:
    api_logging.clear()
