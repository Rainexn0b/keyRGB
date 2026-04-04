from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from .models import ExceptionTransparencyBaseline


_DEBT_BASELINE_PATH = Path("buildpython/config/debt_baselines.json")

_EXCLUDE_PATTERNS = [
    "vendor/",
    "__pycache__/",
    ".git/",
    "htmlcov/",
    "buildlog/",
    ".venv/",
]

COUNT_CATEGORIES = [
    "naked_except",
    "baseexception_catch",
    "broad_except_total",
    "broad_except_traceback_logged",
    "broad_except_logged_no_traceback",
    "broad_except_unlogged",
]


def should_exclude(path: Path, root: Path) -> bool:
    rel = str(path.relative_to(root))
    return any(pattern in rel for pattern in _EXCLUDE_PATTERNS)


def iter_python_files(root: Path) -> Iterable[Path]:
    for folder in [root / "src", root / "buildpython"]:
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            if should_exclude(path, root):
                continue
            yield path


def load_baseline(root: Path) -> ExceptionTransparencyBaseline:
    config_path = root / _DEBT_BASELINE_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ExceptionTransparencyBaseline(counts={}, gated_categories=set())

    section = payload.get("exception_transparency", {})
    counts_raw = section.get("counts", {})
    counts = {
        str(category): int(value)
        for category, value in counts_raw.items()
        if isinstance(category, str) and isinstance(value, int | float)
    }
    gated_categories = {str(category) for category in section.get("gated_categories", []) if isinstance(category, str)}
    return ExceptionTransparencyBaseline(counts=counts, gated_categories=gated_categories)


def baseline_delta(current: int, baseline: int | None) -> str:
    if baseline is None:
        return "n/a"
    return f"{current - baseline:+d}"


def baseline_regressions(
    counts: Counter[str],
    baseline: ExceptionTransparencyBaseline,
) -> list[tuple[str, int, int]]:
    regressions: list[tuple[str, int, int]] = []
    for category in sorted(baseline.gated_categories):
        current = counts.get(category, 0)
        expected = baseline.counts.get(category, 0)
        if current > expected:
            regressions.append((category, current, expected))
    return regressions
