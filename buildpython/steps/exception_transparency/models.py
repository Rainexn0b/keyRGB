from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExceptionTransparencyFinding:
    category: str
    path: str
    line: int
    message: str
    snippet: str


@dataclass(frozen=True)
class ExceptionTransparencyBaseline:
    counts: dict[str, int]
    gated_categories: set[str]
