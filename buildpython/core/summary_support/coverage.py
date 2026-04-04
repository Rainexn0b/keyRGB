from __future__ import annotations

import sys
from pathlib import Path

from .common import coerce_float, coverage_status, read_json_if_exists
from .models import BuildSummary

_USE_COLOR = sys.stdout.isatty()
_RESET = "\033[0m" if _USE_COLOR else ""
_BOLD = "\033[1m" if _USE_COLOR else ""
_DIM = "\033[2m" if _USE_COLOR else ""
_GREEN = "\033[32m" if _USE_COLOR else ""
_RED = "\033[31m" if _USE_COLOR else ""

_SEP = "\u2500" * 60  # ────────────────────────────────────────────────────────────


def _c(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}" if code else text


def build_terminal_coverage_highlight(buildlog_dir: Path) -> str | None:
    coverage = read_json_if_exists(buildlog_dir / "coverage-summary.json")
    if coverage is None:
        return None

    if coverage_status(coverage) == "missing_capture":
        return "Coverage: waiting for pytest coverage capture"

    summary = coverage.get("summary", {})
    if not isinstance(summary, dict):
        return None

    total_percent = coerce_float(summary.get("total_percent", 0.0))
    parts = [f"Coverage: {total_percent:.2f}% total"]

    tracked_prefixes = coverage.get("tracked_prefixes", [])
    if isinstance(tracked_prefixes, list):
        prefix_parts: list[str] = []
        for item in tracked_prefixes[:3]:
            if not isinstance(item, dict):
                continue
            prefix = item.get("prefix")
            percent = item.get("percent")
            if not isinstance(prefix, str):
                continue
            label = prefix.rstrip("/")
            if label.startswith("src/"):
                label = label[4:]
            if isinstance(percent, (int, float)):
                prefix_parts.append(f"{label} {float(percent):.2f}%")
        if prefix_parts:
            parts.extend(prefix_parts)

    return " | ".join(parts)


def build_terminal_build_overview(buildlog_dir: Path, summary: BuildSummary) -> list[str]:
    total_steps = len(summary.steps)
    successful = sum(1 for step in summary.steps if step.status == "success")
    failed = sum(1 for step in summary.steps if step.status == "failure")
    skipped = sum(1 for step in summary.steps if step.status == "skipped")

    bar_width = 20
    filled = max(0, min(bar_width, int(round(summary.health_score / 100 * bar_width))))
    bar = "\u2588" * filled + "\u2591" * (bar_width - filled)  # █ and ░

    status_icon = "\u2705  " if summary.passed else "\u274c  "  # ✅ or ❌
    status_label = _c("PASS", _BOLD + _GREEN) if summary.passed else _c("FAIL", _BOLD + _RED)

    steps_parts = [f"{successful}/{total_steps} steps"]
    if failed:
        steps_parts.append(f"{failed} failed")
    if skipped:
        steps_parts.append(f"{skipped} skipped")
    steps_text = "  \u00b7  ".join(steps_parts)

    lines = [
        _c(_SEP, _DIM),
        "\U0001f4cb  Build Results",
        _c(_SEP, _DIM),
        f"{status_icon}{status_label}  \u00b7  {summary.total_duration_s:.1f}s  \u00b7  {steps_text}  \u00b7  Health {summary.health_score}/100  [{bar}]",
    ]

    coverage_line = build_terminal_coverage_highlight(buildlog_dir)
    if coverage_line is not None:
        lines.append(f"    {coverage_line}")

    return lines
