from __future__ import annotations
from typing import Literal, TypeAlias

from . import integrations


ModuleName: TypeAlias = Literal['other', 'requests']
MODULE_NAMES: tuple[ModuleName, ...] = ('other', 'requests')


class OtherIntegration(integrations.Integration):
    def __init__(self, name: str | None):
        if name not in MODULE_NAMES:
            return

        super().__init__(name)
        self.type = 'other'
