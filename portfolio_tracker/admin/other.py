from ..app import celery
from .integrations import task_logging, ModuleIntegration, Log


MODULE_NAME = 'other'


class Module(ModuleIntegration):
    pass


@celery.task(bind=True, name='other_logging_clear', max_retries=None)
@task_logging
def other_logging_clear(self) -> None:
    module = Module(MODULE_NAME)
    Log.clear({'info': 7, 'debug': 0, 'warning': 60})
    module.logs.set('info', 'Логи очищены', self.name)
