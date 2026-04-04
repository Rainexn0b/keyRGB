from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HygieneIssue:
    category: str
    path: str
    line: int
    message: str
    snippet: str
    suppressed: bool = False


@dataclass(frozen=True)
class HygieneBaseline:
    counts: dict[str, int]
    gated_categories: set[str]
    path_budgets: dict[str, dict[str, int]]
