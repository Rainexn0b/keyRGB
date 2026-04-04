from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from .models import HygieneBaseline, HygieneIssue


EXCLUDE_PATTERNS = [
    "vendor/",
    "__pycache__/",
    ".git/",
    "htmlcov/",
    "buildlog/",
    ".venv/",
]

_DEBT_BASELINE_PATH = Path("buildpython/config/debt_baselines.json")
_BASELINE_LOAD_ERRORS = (OSError, json.JSONDecodeError)


def _should_exclude(path: Path, root: Path) -> bool:
    rel = str(path.relative_to(root))
    return any(excl in rel for excl in EXCLUDE_PATTERNS)


def _iter_python_files(root: Path) -> Iterable[Path]:
    for folder in [root / "src", root / "buildpython"]:
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            if _should_exclude(path, root):
                continue
            yield path


def _load_hygiene_baseline(root: Path) -> HygieneBaseline:
    config_path = root / _DEBT_BASELINE_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except _BASELINE_LOAD_ERRORS:
        return HygieneBaseline(counts={}, gated_categories=set(), path_budgets={})

    section = payload.get("code_hygiene", {})
    counts_raw = section.get("counts", {})
    counts = {str(category): int(value) for category, value in counts_raw.items() if isinstance(value, int | float)}
    gated_categories = {str(category) for category in section.get("gated_categories", []) if isinstance(category, str)}
    path_budgets_raw = section.get("path_budgets", {})
    path_budgets = {
        str(category): {
            str(path): int(value)
            for path, value in budgets.items()
            if isinstance(path, str) and isinstance(value, int | float)
        }
        for category, budgets in path_budgets_raw.items()
        if isinstance(category, str) and isinstance(budgets, dict)
    }
    return HygieneBaseline(counts=counts, gated_categories=gated_categories, path_budgets=path_budgets)


def _baseline_delta(current: int, baseline: int | None) -> str:
    if baseline is None:
        return "n/a"
    delta = current - baseline
    return f"{delta:+d}"


def _baseline_regressions(counts: Counter[str], baseline: HygieneBaseline) -> list[tuple[str, int, int]]:
    regressions: list[tuple[str, int, int]] = []
    for category in sorted(baseline.gated_categories):
        current = counts.get(category, 0)
        expected = baseline.counts.get(category, 0)
        if current > expected:
            regressions.append((category, current, expected))
    return regressions


def _path_budget_regressions(
    issues: list[HygieneIssue],
    baseline: HygieneBaseline,
) -> list[tuple[str, str, int, int]]:
    grouped: dict[str, Counter[str]] = {}
    for issue in issues:
        grouped.setdefault(issue.category, Counter())[issue.path] += 1

    regressions: list[tuple[str, str, int, int]] = []
    for category, budgets in baseline.path_budgets.items():
        current_counts = grouped.get(category, Counter())
        for path, expected in budgets.items():
            current = int(current_counts.get(path, 0))
            if current > expected:
                regressions.append((category, path, current, expected))
    return regressions
