from __future__ import annotations
from typing import TYPE_CHECKING

from portfolio_tracker.admin.models import Api, Key, Stream, Task
from portfolio_tracker.admin.repository import ApiRepository, KeyRepository, \
    StreamRepository, TaskRepository

if TYPE_CHECKING:
    from werkzeug.datastructures.structures import ImmutableMultiDict


class ApiService:

    def __init__(self, api: Api) -> None:
        self.api = api

    def edit(self, form: ImmutableMultiDict) -> None:
        self.api.minute_limit = form.get('minute_limit', 0, type=int)
        self.api.month_limit = form.get('month_limit', 0, type=int)
        self.api.key_prefix = form.get('key_prefix', '', type=str)
        self.api.need_key = form.get('need_key', False, type=bool)
        self.api.need_proxy = form.get('need_proxy', False, type=bool)
        ApiRepository.save(self.api)


class KeyService:

    def __init__(self, key: Key) -> None:
        self.key = key

    def edit(self, form: ImmutableMultiDict) -> None:
        self.key.api_key = form['api_key']
        self.key.comment = form['comment']
        KeyRepository.save(self.key)

    def delete(self) -> None:
        self.key.stream.api_key_id = None
        KeyRepository.delete(self.key)


class StreamService:

    def __init__(self, stream: Stream) -> None:
        self.stream = stream

    def edit(self, form: ImmutableMultiDict) -> None:
        self.stream.next_call = form['next_call']
        self.stream.active = form.get('active', False, type=bool)
        StreamRepository.save(self.stream)

    def delete(self) -> None:
        StreamRepository.delete(self.stream)


class TaskService:

    def __init__(self, task: Task) -> None:
        self.task = task

    def edit(self, form: ImmutableMultiDict) -> None:
        self.task.retry_period_type = form.get('retry_period_type', 0, type=int)
        self.task.retry_period_count = form.get('retry_period_count', 0, type=int)
        TaskRepository.save(self.task)
