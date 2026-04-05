from __future__ import annotations

from pathlib import Path

from .common import coverage_status, file_size_counts, read_json_if_exists


def append_debt_snapshot(lines: list[str], buildlog_dir: Path) -> None:
    hygiene = read_json_if_exists(buildlog_dir / "code-hygiene.json")
    exception_transparency = read_json_if_exists(buildlog_dir / "exception-transparency.json")
    markers = read_json_if_exists(buildlog_dir / "code-markers.json")
    coverage = read_json_if_exists(buildlog_dir / "coverage-summary.json")
    file_size = read_json_if_exists(buildlog_dir / "file-size-analysis.json")

    if (
        hygiene is None
        and exception_transparency is None
        and markers is None
        and coverage is None
        and file_size is None
    ):
        return

    lines.extend(["", "## Debt Snapshot", ""])

    if hygiene is not None:
        active = hygiene.get("active_counts", {})
        suppressed = hygiene.get("suppressed_counts", {})
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
            current = active.get(category)
            if not isinstance(current, int):
                continue
            s = suppressed.get(category, 0)
            supp_text = f" (suppressed {s})" if isinstance(s, int) and s else ""
            lines.append(f"- {category}: {current}{supp_text}")

        if isinstance(top_files, dict):
            for category, label in [
                ("silent_broad_except", "Top silent exception hotspot"),
                ("logged_broad_except", "Top logged exception hotspot"),
                ("fallback_broad_except", "Top fallback exception hotspot"),
                ("cleanup_hotspot", "Top cleanup hotspot"),
            ]:
                hotspots = top_files.get(category, [])
                if not isinstance(hotspots, list) or not hotspots:
                    continue
                item = hotspots[0]
                if isinstance(item, dict):
                    lines.append(f"- {label}: {item.get('path')} ({item.get('count')})")

        lines.append(f"- Report: {buildlog_dir / 'code-hygiene.md'}")
        lines.append("")

    if exception_transparency is not None:
        counts = exception_transparency.get("counts", {})
        waived_total = exception_transparency.get("waived_total", 0)
        top_files = exception_transparency.get("top_files_by_category", {})

        lines.append("### Exception Transparency")
        if isinstance(waived_total, int) and waived_total:
            lines.append(f"- Waived via @quality-exception: {waived_total}")
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
            lines.append(f"- {category}: {current}")

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
        if coverage_status(coverage) == "missing_capture":
            lines.append("- Status: waiting for pytest coverage capture")
            lines.append("- Run: .venv/bin/python -m buildpython --run-steps=2,18")
        else:
            lines.append(f"- Total coverage: {summary.get('total_percent', 0.0)}%")
            minimum_total = baseline.get("minimum_total_percent") if isinstance(baseline, dict) else None
            if minimum_total is not None:
                lines.append(
                    f"- Baseline total: {minimum_total}% (delta {baseline.get('delta_total_percent', 0.0):+.2f}%)"
                )
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

    if file_size is not None:
        file_counts, import_counts, flat_directory_count, delegation_candidate_count = file_size_counts(file_size)
        files = file_size.get("files", [])
        import_blocks = file_size.get("import_blocks", [])
        flat_directories = file_size.get("flat_directories", [])
        delegation_candidates = file_size.get("delegation_candidates", [])

        lines.append("### File Size")
        lines.append(
            "- File buckets: "
            f"refactor={file_counts.get('refactor', 0)}, "
            f"critical={file_counts.get('critical', 0)}, "
            f"severe={file_counts.get('severe', 0)}, "
            f"extreme={file_counts.get('extreme', 0)}"
        )
        lines.append(
            "- Import blocks: "
            f"warning={import_counts.get('warning', 0)}, "
            f"critical={import_counts.get('critical', 0)}, "
            f"severe={import_counts.get('severe', 0)}"
        )
        lines.append(f"- Flat directories: {flat_directory_count}")
        lines.append(f"- Delegation candidates: {delegation_candidate_count}")
        if isinstance(files, list) and files:
            first = files[0]
            if isinstance(first, dict):
                lines.append(f"- Largest file: {first.get('path')} ({first.get('lines')} lines)")
        if isinstance(import_blocks, list) and import_blocks:
            first = import_blocks[0]
            if isinstance(first, dict):
                lines.append(f"- Longest import block: {first.get('path')} ({first.get('lines')} lines)")
        if isinstance(flat_directories, list) and flat_directories:
            first = flat_directories[0]
            if isinstance(first, dict):
                lines.append(
                    f"- Flattest directory: {first.get('path')} ({first.get('direct_python_files')} direct Python files)"
                )
        if isinstance(delegation_candidates, list) and delegation_candidates:
            first = delegation_candidates[0]
            if isinstance(first, dict):
                lines.append(f"- Top delegation candidate: {first.get('path')} (score={first.get('score')})")
        lines.append(f"- Report: {buildlog_dir / 'file-size-analysis.md'}")
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
