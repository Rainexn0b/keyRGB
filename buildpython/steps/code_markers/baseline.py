from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .models import MarkerBaseline


MARKERS = [
    "TODO",
    "FIXME",
    "HACK",
    "NOTE",
    "OPTIMIZE",
    "REVIEW",
]

REF_EXTS = [
    ".new",
    ".old",
    ".bak",
    ".tmp",
    ".v2",
    ".wip",
    ".ref",
    ".archive",
]

DEBT_BASELINE_PATH = Path("buildpython/config/debt_baselines.json")


def load_marker_baseline(root: Path) -> MarkerBaseline:
    config_path = root / DEBT_BASELINE_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return MarkerBaseline(counts={}, gated_markers=set())

    section = payload.get("code_markers", {})
    counts_raw = section.get("marker_counts", {})
    counts = {str(marker): int(value) for marker, value in counts_raw.items() if isinstance(value, int | float)}
    gated_markers = {str(marker) for marker in section.get("gated_markers", []) if isinstance(marker, str)}
    return MarkerBaseline(counts=counts, gated_markers=gated_markers)


def marker_delta(current: int, baseline: int | None) -> str:
    if baseline is None:
        return "n/a"
    delta = current - baseline
    return f"{delta:+d}"


def marker_regressions(counts: Counter[str], baseline: MarkerBaseline) -> list[tuple[str, int, int]]:
    regressions: list[tuple[str, int, int]] = []
    for marker in sorted(baseline.gated_markers):
        current = counts.get(marker, 0)
        expected = baseline.counts.get(marker, 0)
        if current > expected:
            regressions.append((marker, current, expected))
    return regressions
