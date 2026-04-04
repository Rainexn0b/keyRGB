from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from .summary_support.coverage import build_terminal_build_overview, build_terminal_coverage_highlight
from .summary_support.debt_markdown import append_debt_snapshot
from .summary_support.models import BuildSummary, StepSummary


def write_summary(buildlog_dir: Path, summary: BuildSummary) -> None:
    buildlog_dir.mkdir(parents=True, exist_ok=True)

    json_path = buildlog_dir / "build-summary.json"
    md_path = buildlog_dir / "build-summary.md"

    json_path.write_text(json.dumps(asdict(summary), indent=2) + "\n", encoding="utf-8")

    lines: list[str] = []
    lines.append("# Build summary")
    lines.append("")
    lines.append(f"- Passed: {'yes' if summary.passed else 'no'}")
    lines.append(f"- Health: {summary.health_score}/100")
    lines.append(f"- Duration: {summary.total_duration_s:.1f}s")

    bar_width = 20
    filled = max(0, min(bar_width, int(round(summary.health_score / 100 * bar_width))))
    bar = "[" + ("#" * filled) + ("-" * (bar_width - filled)) + "]"
    lines.append(f"- Health bar: {bar}")
    lines.append("")
    lines.append("| Step | Name | Status | Duration | Exit |")
    lines.append("|---:|---|---|---:|---:|")

    for s in summary.steps:
        lines.append(f"| {s.number} | {s.name} | {s.status} | {s.duration_s:.1f}s | {s.exit_code} |")

    append_debt_snapshot(lines, buildlog_dir)

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
