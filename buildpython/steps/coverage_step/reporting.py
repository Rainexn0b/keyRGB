from __future__ import annotations

from pathlib import Path
from typing import Any

from ..reports import write_csv, write_json, write_md
from .constants import _SUMMARY_CSV_NAME, _SUMMARY_JSON_NAME, _SUMMARY_MD_NAME


def _build_stdout(report: dict[str, Any], *, reports_path: Path) -> list[str]:
    lines = [
        "Coverage summary",
        "",
    ]
    summary = report.get("summary", {})
    baseline = report.get("baseline", {})
    total_percent = float(summary.get("total_percent", 0.0))
    minimum_total = baseline.get("minimum_total_percent")
    delta_total = baseline.get("delta_total_percent")
    baseline_text = "-" if minimum_total is None else f"{float(minimum_total):.2f}%"
    delta_text = "n/a" if delta_total is None else f"{float(delta_total):+.2f}%"
    lines.append(
        f"Total: {total_percent:.2f}%  baseline={baseline_text} delta={delta_text} "
        f"({summary.get('covered_lines', 0)}/{summary.get('num_statements', 0)} lines)"
    )

    tracked_prefixes = report.get("tracked_prefixes", [])
    if isinstance(tracked_prefixes, list) and tracked_prefixes:
        lines.append("")
        lines.append("Tracked prefixes:")
        for item in tracked_prefixes:
            prefix = item.get("prefix")
            percent = item.get("percent")
            expected = item.get("baseline")
            delta = item.get("delta")
            if not isinstance(prefix, str):
                continue
            status = "FAIL" if item.get("status") == "fail" else "OK"
            lines.append(
                f"  {prefix}: {float(percent):.2f}% baseline={float(expected):.2f}% delta={float(delta):+.2f}% [{status}]"
            )

    watch_files = report.get("watch_files", [])
    if isinstance(watch_files, list) and watch_files:
        lines.append("")
        lines.append("Watch files:")
        for item in watch_files:
            path = item.get("path")
            if not isinstance(path, str):
                continue
            percent = item.get("percent")
            if percent is None:
                lines.append(f"  {path}: not present in coverage payload")
                continue
            lines.append(f"  {path}: {float(percent):.2f}%")

    lowest = report.get("lowest_covered_files", [])
    if isinstance(lowest, list) and lowest:
        lines.append("")
        lines.append("Lowest-covered files:")
        for item in lowest[:10]:
            path = item.get("path")
            percent = item.get("percent")
            statements = item.get("num_statements")
            if isinstance(path, str):
                lines.append(f"  {path}: {float(percent):.2f}% ({statements} statements)")

    regressions = baseline.get("regressions", [])
    if isinstance(regressions, list) and regressions:
        lines.append("")
        lines.append("Coverage regressions:")
        for item in regressions:
            kind = item.get("kind")
            target = item.get("target")
            current = item.get("current")
            expected = item.get("baseline")
            if isinstance(kind, str) and isinstance(target, str):
                lines.append(f"  {kind} {target}: {float(current):.2f}% < baseline {float(expected):.2f}%")
    else:
        lines.append("")
        lines.append("Coverage regressions: none")

    lines.append("")
    lines.append(f"Reports: {reports_path / _SUMMARY_MD_NAME}")
    return lines


def _write_coverage_reports(*, report_dir: Path, report: dict[str, Any]) -> None:
    write_json(report_dir / _SUMMARY_JSON_NAME, report)

    write_csv(
        report_dir / _SUMMARY_CSV_NAME,
        ["path", "percent", "covered_lines", "num_statements", "watched"],
        [
            [
                str(item.get("path", "")),
                "" if item.get("percent") is None else f"{float(item.get('percent', 0.0)):.2f}",
                str(item.get("covered_lines", 0)),
                str(item.get("num_statements", 0)),
                "yes",
            ]
            for item in report.get("watch_files", [])
        ]
        + [
            [
                str(item.get("path", "")),
                f"{float(item.get('percent', 0.0)):.2f}",
                str(item.get("covered_lines", 0)),
                str(item.get("num_statements", 0)),
                "no",
            ]
            for item in report.get("lowest_covered_files", [])
        ],
    )

    summary = report.get("summary", {})
    baseline = report.get("baseline", {})
    md_lines = [
        "# Coverage summary",
        "",
        f"- Total coverage: {float(summary.get('total_percent', 0.0)):.2f}%",
        f"- Covered lines: {summary.get('covered_lines', 0)}",
        f"- Statements: {summary.get('num_statements', 0)}",
        f"- Files: {summary.get('files', 0)}",
        "",
    ]

    minimum_total = baseline.get("minimum_total_percent")
    if minimum_total is not None:
        md_lines.append(f"- Baseline total: {float(minimum_total):.2f}%")
        md_lines.append(f"- Delta vs baseline: {float(baseline.get('delta_total_percent', 0.0)):+.2f}%")
        md_lines.append("")

    tracked_prefixes = report.get("tracked_prefixes", [])
    if isinstance(tracked_prefixes, list) and tracked_prefixes:
        md_lines.extend(
            [
                "## Tracked prefixes",
                "",
                "| Prefix | Coverage | Baseline | Delta | Status |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for item in tracked_prefixes:
            md_lines.append(
                f"| {item.get('prefix')} | {float(item.get('percent', 0.0)):.2f}% | "
                f"{float(item.get('baseline', 0.0)):.2f}% | {float(item.get('delta', 0.0)):+.2f}% | "
                f"{'FAIL' if item.get('status') == 'fail' else 'OK'} |"
            )
        md_lines.append("")

    watch_files = report.get("watch_files", [])
    if isinstance(watch_files, list) and watch_files:
        md_lines.extend(
            [
                "## Watch files",
                "",
                "| File | Coverage | Covered | Statements | Status |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for item in watch_files:
            percent = item.get("percent")
            percent_text = "-" if percent is None else f"{float(percent):.2f}%"
            md_lines.append(
                f"| {item.get('path')} | {percent_text} | {item.get('covered_lines', 0)} | "
                f"{item.get('num_statements', 0)} | {item.get('status')} |"
            )
        md_lines.append("")

    lowest = report.get("lowest_covered_files", [])
    if isinstance(lowest, list) and lowest:
        md_lines.extend(
            [
                "## Lowest-covered files",
                "",
                "| File | Coverage | Covered | Statements |",
                "|---|---:|---:|---:|",
            ]
        )
        for item in lowest:
            md_lines.append(
                f"| {item.get('path')} | {float(item.get('percent', 0.0)):.2f}% | {item.get('covered_lines', 0)} | "
                f"{item.get('num_statements', 0)} |"
            )
        md_lines.append("")

    regressions = baseline.get("regressions", [])
    if isinstance(regressions, list) and regressions:
        md_lines.extend(
            [
                "## Regressions",
                "",
                "| Kind | Target | Current | Baseline |",
                "|---|---|---:|---:|",
            ]
        )
        for item in regressions:
            md_lines.append(
                f"| {item.get('kind')} | {item.get('target')} | {float(item.get('current', 0.0)):.2f}% | "
                f"{float(item.get('baseline', 0.0)):.2f}% |"
            )
    else:
        md_lines.extend(["## Regressions", "", "No coverage regressions detected."])

    write_md(report_dir / _SUMMARY_MD_NAME, md_lines)


def _write_missing_capture_reports(*, report_dir: Path) -> None:
    payload = {
        "summary": {
            "status": "missing_capture",
            "total_percent": None,
            "covered_lines": None,
            "num_statements": None,
            "files": 0,
        },
        "baseline": {
            "minimum_total_percent": None,
            "delta_total_percent": None,
            "tracked_prefixes": {},
            "regressions": [],
        },
        "tracked_prefixes": [],
        "watch_files": [],
        "lowest_covered_files": [],
    }
    write_json(report_dir / _SUMMARY_JSON_NAME, payload)
    write_csv(
        report_dir / _SUMMARY_CSV_NAME,
        ["path", "percent", "covered_lines", "num_statements", "watched"],
        [],
    )
    write_md(
        report_dir / _SUMMARY_MD_NAME,
        [
            "# Coverage summary",
            "",
            "No fresh pytest coverage capture was found.",
            "",
            "Run one of:",
            "",
            "```bash",
            ".venv/bin/python -m buildpython --run-steps=2,18",
            ".venv/bin/python -m buildpython --profile debt",
            ".venv/bin/python -m buildpython --profile full",
            "```",
        ],
    )
