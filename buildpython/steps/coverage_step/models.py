from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CoverageBaseline:
    minimum_total_percent: float | None
    tracked_prefixes: dict[str, float]
    watch_files: tuple[str, ...]
    minimum_watch_file_percent: float = 0.0
    # Backward-compatible per-file non-regression thresholds, e.g. for the
    # extensionless installed helper which shares no keyrgb/ prefix.
    per_file_minimums: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CoverageRegression:
    kind: str
    target: str
    current: float
    baseline: float
