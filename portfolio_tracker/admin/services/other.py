from datetime import datetime
from portfolio_tracker.app import celery
from portfolio_tracker.admin.services.integrations import task_logging, Log
from portfolio_tracker.admin.services.integrations_other import OtherIntegration


MODULE_NAME = 'other'


@celery.task(bind=True, name='other_logging_clear', max_retries=None)
@task_logging
def other_logging_clear(self) -> None:
    module = OtherIntegration(MODULE_NAME)
    Log.clear({'info': 7, 'debug': 0, 'warning': 60})

    # Инфо
    module.info.set('Логи очищены', datetime.now())
