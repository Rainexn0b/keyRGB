from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StepSummary:
    number: int
    name: str
    status: str  # success|failure|skipped
    exit_code: int
    duration_s: float


@dataclass(frozen=True)
class BuildSummary:
    passed: bool
    health_score: int  # 0-100
    total_duration_s: float
    steps: list[StepSummary]


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _coverage_status(coverage: dict[str, Any]) -> str | None:
    summary = coverage.get("summary", {})
    if not isinstance(summary, dict):
        return None
    status = summary.get("status")
    return status if isinstance(status, str) else None


def _coerce_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def build_terminal_coverage_highlight(buildlog_dir: Path) -> str | None:
    coverage = _read_json_if_exists(buildlog_dir / "coverage-summary.json")
    if coverage is None:
        return None

    if _coverage_status(coverage) == "missing_capture":
        return "Coverage: waiting for pytest coverage capture"

    summary = coverage.get("summary", {})
    if not isinstance(summary, dict):
        return None

    total_percent = _coerce_float(summary.get("total_percent", 0.0))
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
    bar = "[" + ("#" * filled) + ("-" * (bar_width - filled)) + "]"

    lines = [
        "Build summary:",
        f"  Status: {'PASS' if summary.passed else 'FAIL'}",
        f"  Steps: {total_steps} total | {successful} successful | {failed} failed | {skipped} skipped",
        f"  Duration: {summary.total_duration_s:.1f}s",
        f"  Health: {summary.health_score}/100 {bar}",
    ]

    coverage_line = build_terminal_coverage_highlight(buildlog_dir)
    if coverage_line is not None:
        lines.append(f"  {coverage_line}")

    return lines


def _append_debt_snapshot(lines: list[str], buildlog_dir: Path) -> None:
    hygiene = _read_json_if_exists(buildlog_dir / "code-hygiene.json")
    exception_transparency = _read_json_if_exists(buildlog_dir / "exception-transparency.json")
    markers = _read_json_if_exists(buildlog_dir / "code-markers.json")
    coverage = _read_json_if_exists(buildlog_dir / "coverage-summary.json")

    if hygiene is None and exception_transparency is None and markers is None and coverage is None:
        return

    lines.extend(["", "## Debt Snapshot", ""])

    if hygiene is not None:
        counts = hygiene.get("counts", {})
        baseline = hygiene.get("baseline", {})
        baseline_counts = baseline.get("counts", {}) if isinstance(baseline, dict) else {}
        regressions = baseline.get("regressions", []) if isinstance(baseline, dict) else []
        top_files = hygiene.get("top_files_by_category", {})

        lines.append("### Code Hygiene")
        for category in [
            "silent_broad_except",
            "logged_broad_except",
            "fallback_broad_except",
            "cleanup_hotspot",
            "resource_leak",
            "forbidden_api",
            "forbidden_getattr",
        ]:
            current = counts.get(category)
            if not isinstance(current, int):
                continue
            baseline_count = baseline_counts.get(category)
            delta = "n/a"
            if isinstance(baseline_count, int):
                delta = f"{current - baseline_count:+d}"
            lines.append(f"- {category}: {current} (delta {delta})")

        if isinstance(regressions, list) and regressions:
            lines.append("- Regressions:")
            for item in regressions[:10]:
                if not isinstance(item, dict):
                    continue
                regression_category = item.get("category")
                current = item.get("current")
                expected = item.get("baseline")
                if not isinstance(regression_category, str):
                    continue
                lines.append(f"  - {regression_category}: {current} > baseline {expected}")
        else:
            lines.append("- Regressions: none")

        path_regressions = baseline.get("path_budget_regressions", []) if isinstance(baseline, dict) else []
        if isinstance(path_regressions, list) and path_regressions:
            lines.append("- Path budget regressions:")
            for item in path_regressions[:10]:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"  - {item.get('category')} {item.get('path')}: {item.get('current')} > baseline {item.get('baseline')}"
                )
        else:
            lines.append("- Path budget regressions: none")

        if isinstance(top_files, dict):
            exception_hotspots = top_files.get("silent_broad_except", [])
            logged_hotspots = top_files.get("logged_broad_except", [])
            fallback_hotspots = top_files.get("fallback_broad_except", [])
            cleanup_hotspots = top_files.get("cleanup_hotspot", [])
            if isinstance(exception_hotspots, list) and exception_hotspots:
                item = exception_hotspots[0]
                if isinstance(item, dict):
                    lines.append(f"- Top silent exception hotspot: {item.get('path')} ({item.get('count')})")
            if isinstance(logged_hotspots, list) and logged_hotspots:
                item = logged_hotspots[0]
                if isinstance(item, dict):
                    lines.append(f"- Top logged exception hotspot: {item.get('path')} ({item.get('count')})")
            if isinstance(fallback_hotspots, list) and fallback_hotspots:
                item = fallback_hotspots[0]
                if isinstance(item, dict):
                    lines.append(f"- Top fallback exception hotspot: {item.get('path')} ({item.get('count')})")
            if isinstance(cleanup_hotspots, list) and cleanup_hotspots:
                item = cleanup_hotspots[0]
                if isinstance(item, dict):
                    lines.append(f"- Top cleanup hotspot: {item.get('path')} ({item.get('count')})")

        lines.append(f"- Report: {buildlog_dir / 'code-hygiene.md'}")
        lines.append("")

    if exception_transparency is not None:
        counts = exception_transparency.get("counts", {})
        baseline = exception_transparency.get("baseline", {})
        baseline_counts = baseline.get("counts", {}) if isinstance(baseline, dict) else {}
        regressions = baseline.get("regressions", []) if isinstance(baseline, dict) else []
        top_files = exception_transparency.get("top_files_by_category", {})

        lines.append("### Exception Transparency")
        for category in [
            "naked_except",
            "baseexception_catch",
            "broad_except_total",
            "broad_except_traceback_logged",
            "broad_except_logged_no_traceback",
            "broad_except_unlogged",
        ]:
            current = counts.get(category)
            if not isinstance(current, int):
                continue
            baseline_count = baseline_counts.get(category)
            delta = "n/a"
            if isinstance(baseline_count, int):
                delta = f"{current - baseline_count:+d}"
            lines.append(f"- {category}: {current} (delta {delta})")

        if isinstance(regressions, list) and regressions:
            lines.append("- Regressions:")
            for item in regressions[:10]:
                if not isinstance(item, dict):
                    continue
                reg_category = item.get("category")
                current = item.get("current")
                expected = item.get("baseline")
                if not isinstance(reg_category, str):
                    continue
                lines.append(f"  - {reg_category}: {current} > baseline {expected}")
        else:
            lines.append("- Regressions: none")

        if isinstance(top_files, dict):
            for category, label in [
                ("broad_except_unlogged", "Top unlogged broad catch hotspot"),
                ("broad_except_logged_no_traceback", "Top no-traceback hotspot"),
                ("broad_except_total", "Top broad catch hotspot"),
            ]:
                hotspots = top_files.get(category, [])
                if not isinstance(hotspots, list) or not hotspots:
                    continue
                item = hotspots[0]
                if isinstance(item, dict):
                    lines.append(f"- {label}: {item.get('path')} ({item.get('count')})")

        lines.append(f"- Report: {buildlog_dir / 'exception-transparency.md'}")
        lines.append("")

    if coverage is not None:
        summary = coverage.get("summary", {})
        baseline = coverage.get("baseline", {})
        regressions = baseline.get("regressions", []) if isinstance(baseline, dict) else []
        lines.append("### Coverage")
        if _coverage_status(coverage) == "missing_capture":
            lines.append("- Status: waiting for pytest coverage capture")
            lines.append("- Run: .venv/bin/python -m buildpython --run-steps=2,18")
        else:
            lines.append(f"- Total coverage: {summary.get('total_percent', 0.0)}%")
            minimum_total = baseline.get("minimum_total_percent") if isinstance(baseline, dict) else None
            if minimum_total is not None:
                lines.append(f"- Baseline total: {minimum_total}% (delta {baseline.get('delta_total_percent', 0.0):+.2f}%)")
            if isinstance(regressions, list) and regressions:
                lines.append("- Regressions:")
                for item in regressions[:10]:
                    if not isinstance(item, dict):
                        continue
                    lines.append(
                        f"  - {item.get('kind')} {item.get('target')}: {item.get('current')} < baseline {item.get('baseline')}"
                    )
            else:
                lines.append("- Regressions: none")
        lines.append(f"- Report: {buildlog_dir / 'coverage-summary.md'}")
        lines.append("")

    if markers is not None:
        marker_counts = markers.get("marker_counts", {})
        baseline = markers.get("baseline", {})
        baseline_counts = baseline.get("marker_counts", {}) if isinstance(baseline, dict) else {}
        regressions = baseline.get("regressions", []) if isinstance(baseline, dict) else []

        lines.append("### Code Markers")
        for marker in ["TODO", "FIXME", "HACK", "NOTE"]:
            current = marker_counts.get(marker)
            if not isinstance(current, int):
                continue
            baseline_count = baseline_counts.get(marker)
            delta = "n/a"
            if isinstance(baseline_count, int):
                delta = f"{current - baseline_count:+d}"
            lines.append(f"- {marker}: {current} (delta {delta})")

        if isinstance(regressions, list) and regressions:
            lines.append("- Regressions:")
            for item in regressions[:10]:
                if not isinstance(item, dict):
                    continue
                regression_marker = item.get("marker")
                current = item.get("current")
                expected = item.get("baseline")
                if not isinstance(regression_marker, str):
                    continue
                lines.append(f"  - {regression_marker}: {current} > baseline {expected}")
        else:
            lines.append("- Regressions: none")

        lines.append(f"- Report: {buildlog_dir / 'code-markers.md'}")

    debt_index = buildlog_dir / "debt-index.md"
    if debt_index.exists():
        lines.extend(["", f"- Combined debt index: {debt_index}"])


def build_terminal_debt_snapshot(buildlog_dir: Path, *, include_coverage: bool = True) -> list[str]:
    lines: list[str] = []
    hygiene = _read_json_if_exists(buildlog_dir / "code-hygiene.json")
    exception_transparency = _read_json_if_exists(buildlog_dir / "exception-transparency.json")
    markers = _read_json_if_exists(buildlog_dir / "code-markers.json")
    coverage = _read_json_if_exists(buildlog_dir / "coverage-summary.json")

    if hygiene is None and exception_transparency is None and markers is None and coverage is None:
        return lines

    lines.append("Debt snapshot:")

    if hygiene is not None:
        counts = hygiene.get("counts", {})
        baseline = hygiene.get("baseline", {})
        baseline_counts = baseline.get("counts", {}) if isinstance(baseline, dict) else {}
        top_files = hygiene.get("top_files_by_category", {})
        parts: list[str] = []
        for category in [
            "silent_broad_except",
            "logged_broad_except",
            "fallback_broad_except",
            "cleanup_hotspot",
            "resource_leak",
            "forbidden_api",
            "forbidden_getattr",
        ]:
            current = counts.get(category)
            if not isinstance(current, int):
                continue
            baseline_count = baseline_counts.get(category)
            delta = "n/a"
            if isinstance(baseline_count, int):
                delta = f"{current - baseline_count:+d}"
            parts.append(f"{category}={current} ({delta})")
        if parts:
            lines.append("  Hygiene: " + ", ".join(parts))

        if isinstance(top_files, dict):
            for category, label in [
                ("silent_broad_except", "Top silent"),
                ("logged_broad_except", "Top logged"),
                ("fallback_broad_except", "Top fallback"),
                ("cleanup_hotspot", "Top cleanup"),
            ]:
                hotspots = top_files.get(category, [])
                if not isinstance(hotspots, list) or not hotspots:
                    continue
                first = hotspots[0]
                if not isinstance(first, dict):
                    continue
                path = first.get("path")
                count = first.get("count")
                if isinstance(path, str):
                    lines.append(f"  {label}: {path} ({count})")

        path_regressions = baseline.get("path_budget_regressions", []) if isinstance(baseline, dict) else []
        if isinstance(path_regressions, list) and path_regressions:
            first = path_regressions[0]
            if isinstance(first, dict):
                lines.append(
                    "  Path budget regression: "
                    f"{first.get('category')} {first.get('path')} ({first.get('current')} > {first.get('baseline')})"
                )

    if exception_transparency is not None:
        counts = exception_transparency.get("counts", {})
        baseline = exception_transparency.get("baseline", {})
        baseline_counts = baseline.get("counts", {}) if isinstance(baseline, dict) else {}
        et_parts: list[str] = []
        for category in [
            "broad_except_total",
            "broad_except_unlogged",
            "broad_except_logged_no_traceback",
            "broad_except_traceback_logged",
            "naked_except",
            "baseexception_catch",
        ]:
            current = counts.get(category)
            if not isinstance(current, int):
                continue
            baseline_count = baseline_counts.get(category)
            delta = "n/a"
            if isinstance(baseline_count, int):
                delta = f"{current - baseline_count:+d}"
            et_parts.append(f"{category}={current} ({delta})")
        if et_parts:
            lines.append("  Exception transparency: " + ", ".join(et_parts))

        top_files = exception_transparency.get("top_files_by_category", {})
        if isinstance(top_files, dict):
            for category, label in [
                ("broad_except_unlogged", "Top unlogged broad catch"),
                ("broad_except_logged_no_traceback", "Top no-traceback catch"),
                ("broad_except_total", "Top broad catch"),
            ]:
                hotspots = top_files.get(category, [])
                if not isinstance(hotspots, list) or not hotspots:
                    continue
                first = hotspots[0]
                if not isinstance(first, dict):
                    continue
                path = first.get("path")
                count = first.get("count")
                if isinstance(path, str):
                    lines.append(f"  {label}: {path} ({count})")

        regressions = baseline.get("regressions", []) if isinstance(baseline, dict) else []
        if isinstance(regressions, list) and regressions:
            first = regressions[0]
            if isinstance(first, dict):
                lines.append(
                    "  Exception regression: "
                    f"{first.get('category')} ({first.get('current')} > {first.get('baseline')})"
                )

    if coverage is not None and include_coverage:
        if _coverage_status(coverage) == "missing_capture":
            lines.append("  Coverage: missing capture (run --run-steps=2,18 or --profile debt)")
        else:
            summary = coverage.get("summary", {})
            baseline = coverage.get("baseline", {})
            total_raw = summary.get("total_percent", 0.0)
            total_percent = float(total_raw) if isinstance(total_raw, (int, float)) else 0.0
            delta_raw = baseline.get("delta_total_percent") if isinstance(baseline, dict) else None
            delta_text = "n/a"
            if isinstance(delta_raw, (int, float)):
                delta_text = f"{float(delta_raw):+.2f}"
            lines.append(f"  Coverage: total={total_percent:.2f}% ({delta_text})")

            regressions = baseline.get("regressions", []) if isinstance(baseline, dict) else []
            if isinstance(regressions, list) and regressions:
                first = regressions[0]
                if isinstance(first, dict):
                    lines.append(
                        "  Coverage regression: "
                        f"{first.get('kind')} {first.get('target')} ({first.get('current')} < {first.get('baseline')})"
                    )

    if markers is not None:
        marker_counts = markers.get("marker_counts", {})
        baseline = markers.get("baseline", {})
        baseline_counts = baseline.get("marker_counts", {}) if isinstance(baseline, dict) else {}
        top_marker_files = markers.get("top_marker_files", {})
        parts = []
        for marker in ["TODO", "FIXME", "HACK", "NOTE"]:
            current = marker_counts.get(marker)
            if not isinstance(current, int):
                continue
            baseline_count = baseline_counts.get(marker)
            delta = "n/a"
            if isinstance(baseline_count, int):
                delta = f"{current - baseline_count:+d}"
            parts.append(f"{marker}={current} ({delta})")
        if parts:
            lines.append("  Markers: " + ", ".join(parts))

        if isinstance(top_marker_files, dict):
            for marker in ["HACK", "FIXME", "TODO", "NOTE"]:
                hotspots = top_marker_files.get(marker, [])
                if not isinstance(hotspots, list) or not hotspots:
                    continue
                first = hotspots[0]
                if not isinstance(first, dict):
                    continue
                path = first.get("path")
                count = first.get("count")
                if isinstance(path, str):
                    lines.append(f"  Top {marker}: {path} ({count})")

    lines.append(f"  Reports: {buildlog_dir / 'code-hygiene.md'}")
    lines.append(f"           {buildlog_dir / 'code-markers.md'}")
    if coverage is not None:
        lines.append(f"           {buildlog_dir / 'coverage-summary.md'}")
    debt_index = buildlog_dir / "debt-index.md"
    if debt_index.exists():
        lines.append(f"           {debt_index}")
    return lines


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

    _append_debt_snapshot(lines, buildlog_dir)

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
