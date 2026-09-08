from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .summary_support.coverage import build_terminal_build_overview, build_terminal_coverage_highlight
from .summary_support.debt_markdown import append_debt_snapshot
from .summary_support.models import BuildSummary, StepSummary

__all__ = [
    "BuildSummary",
    "StepSummary",
    "build_terminal_build_overview",
    "build_terminal_coverage_highlight",
    "write_summary",
]


def write_summary(buildlog_dir: Path, summary: BuildSummary) -> None:
    buildlog_dir.mkdir(parents=True, exist_ok=True)

    json_path = buildlog_dir / "build-summary.json"
    md_path = buildlog_dir / "build-summary.md"

    json_path.write_text(
        json.dumps(
            {
                **asdict(summary),
                "schema_version": 2,
                "status": summary.status,
                "passed": summary.passed,
                "exit_code": summary.exit_code,
                "counts": summary.counts,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    lines: list[str] = []
    lines.append("# Build summary")
    lines.append("")
    lines.append(f"- Run: {summary.run_id}")
    lines.append(f"- Started (UTC): {summary.started_at}")
    lines.append(f"- Status: {summary.status}")
    lines.append(f"- Exit code: {summary.exit_code if summary.completed else 'not yet available'}")
    lines.append(f"- Duration: {summary.total_duration_s:.1f}s")
    lines.append(
        f"- Selected steps: {len(summary.steps)}; "
        + "; ".join(f"{key}: {value}" for key, value in summary.counts.items())
    )
    lines.append("- Scope: selected checks only; skipped and unselected checks provide no verification.")
    lines.append("")
    lines.append("Health scores start at 100 and deduct points per finding; they do not determine gate status.")
    lines.append("")
    lines.append("| Step | Name | Status | Duration | Exit | Health (penalty score) | Detail |")
    lines.append("|---:|---|---|---:|---:|---:|---|")

    for s in summary.steps:
        health = f"{s.health.score:g}%" if s.health is not None else "—"
        lines.append(
            f"| {s.number} | {s.name} | {s.status} | {s.duration_s:.1f}s | "
            f"{s.exit_code if s.exit_code is not None else '—'} | {health} | {s.message} |"
        )

    append_debt_snapshot(lines, buildlog_dir, report_names=summary.report_names)

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
