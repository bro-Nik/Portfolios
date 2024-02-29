from __future__ import annotations
from typing import Literal, TypeAlias


ModuleName: TypeAlias = Literal['other']
MODULE_NAMES: tuple[ModuleName, ...] = ('other',)


class ModuleIntegration:
    def __init__(self, name: str | None):
        from .integrations import Log
        if name not in MODULE_NAMES:
            return

        self.logs = Log(name)
