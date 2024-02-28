from ..app import celery
from .api_integration import Log, task_logging
from . import currency, stocks, crypto, proxy


@celery.task(bind=True, name='api_logging_clear', max_retries=None)
@task_logging
def api_logging_clear(self) -> None:
    Log.clear({'info': 7, 'debug': 0, 'warning': 60})
