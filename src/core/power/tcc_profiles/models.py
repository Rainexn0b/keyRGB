from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TccProfile:
    id: str
    name: str
    description: str = ""


class TccProfileWriteError(RuntimeError):
    pass
