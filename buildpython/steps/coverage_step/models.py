from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoverageBaseline:
    minimum_total_percent: float | None
    tracked_prefixes: dict[str, float]
    watch_files: tuple[str, ...]
    minimum_watch_file_percent: float = 0.0


@dataclass(frozen=True)
class CoverageRegression:
    kind: str
    target: str
    current: float
    baseline: float
