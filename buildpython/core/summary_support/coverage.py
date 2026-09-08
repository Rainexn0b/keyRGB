from __future__ import annotations

import sys
from pathlib import Path

from .common import coverage_status, read_json_if_exists
from .models import BuildSummary

_USE_COLOR = sys.stdout.isatty()
_RESET = "\033[0m" if _USE_COLOR else ""
_BOLD = "\033[1m" if _USE_COLOR else ""
_DIM = "\033[2m" if _USE_COLOR else ""
_GREEN = "\033[32m" if _USE_COLOR else ""
_YELLOW = "\033[33m" if _USE_COLOR else ""
_RED = "\033[31m" if _USE_COLOR else ""

_SEP = "\u2500" * 60  # ────────────────────────────────────────────────────────────


def _c(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}" if code else text


def build_terminal_coverage_highlight(buildlog_dir: Path, *, report_names: tuple[str, ...] | None = None) -> str | None:
    coverage = read_json_if_exists(buildlog_dir / "coverage-summary.json", report_names=report_names)
    if coverage is None:
        return None

    if coverage_status(coverage) == "missing_capture":
        return "Coverage: unavailable — no successful pytest capture in this run"

    summary = coverage.get("summary", {})
    if not isinstance(summary, dict):
        return None

    total_percent = summary.get("total_percent")
    if not isinstance(total_percent, (int, float)):
        return "Coverage: unavailable — report has no measured percentage"
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
            label = label.removeprefix("keyrgb/")
            if isinstance(percent, (int, float)):
                prefix_parts.append(f"{label} {float(percent):.2f}%")
        if prefix_parts:
            parts.extend(prefix_parts)

    return " | ".join(parts)


def build_terminal_build_overview(buildlog_dir: Path, summary: BuildSummary) -> list[str]:
    counts = summary.counts
    labels = {
        "passed": "PASS",
        "failed": "FAIL",
        "partial": "PARTIAL",
        "not_run": "NOT RUN",
        "incomplete": "INCOMPLETE",
    }
    color = _GREEN if summary.passed else _RED if summary.status == "failed" else _YELLOW
    status_label = _c(labels[summary.status], _BOLD + color)
    steps_text = " · ".join(
        f"{counts[key]} {label}"
        for key, label in (("success", "passed"), ("failure", "failed"), ("skipped", "skipped"), ("not_run", "not run"))
    )
    lines = [
        _c(_SEP, _DIM),
        "📋  Build Results",
        _c(_SEP, _DIM),
        f"{status_label} · {summary.total_duration_s:.1f}s · {len(summary.steps)} selected · {steps_text}",
    ]
    if summary.status in {"partial", "not_run"}:
        lines.append("    Skipped checks were not verified; exit code 0 means no executed check failed.")
    coverage_line = build_terminal_coverage_highlight(buildlog_dir, report_names=summary.report_names)
    if coverage_line is not None:
        lines.append(f"    {coverage_line}")
    return lines
