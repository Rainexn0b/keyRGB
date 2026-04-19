from __future__ import annotations

from pathlib import Path

from .common import (
    coverage_status,
    file_size_counts,
    file_size_structure_candidate_counts,
    loc_bucket_parts,
    loc_check_counts,
    read_json_if_exists,
)


def _annotation_inventory_summary(exception_transparency: dict[str, object]) -> tuple[int | None, list[str]]:
    annotation_inventory = exception_transparency.get("annotation_inventory", {})
    if not isinstance(annotation_inventory, dict):
        return None, []

    total = annotation_inventory.get("total")
    raw_subtrees = annotation_inventory.get("by_subtree", [])
    subtree_bits: list[str] = []
    if isinstance(raw_subtrees, list):
        for item in raw_subtrees[:3]:
            if not isinstance(item, dict):
                continue
            subtree = item.get("subtree")
            count = item.get("count")
            if isinstance(subtree, str) and isinstance(count, int):
                subtree_bits.append(f"{subtree} ({count})")

    return total if isinstance(total, int) else None, subtree_bits


def append_debt_snapshot(lines: list[str], buildlog_dir: Path) -> None:
    hygiene = read_json_if_exists(buildlog_dir / "code-hygiene.json")
    exception_transparency = read_json_if_exists(buildlog_dir / "exception-transparency.json")
    markers = read_json_if_exists(buildlog_dir / "code-markers.json")
    coverage = read_json_if_exists(buildlog_dir / "coverage-summary.json")
    file_size = read_json_if_exists(buildlog_dir / "file-size-analysis.json")
    loc_check = read_json_if_exists(buildlog_dir / "loc-check.json")

    if (
        hygiene is None
        and exception_transparency is None
        and markers is None
        and coverage is None
        and file_size is None
        and loc_check is None
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
        inventory_total, subtree_bits = _annotation_inventory_summary(exception_transparency)
        top_files = exception_transparency.get("top_files_by_category", {})

        lines.append("### Exception Transparency")
        if isinstance(waived_total, int) and waived_total:
            lines.append(f"- Waived via @quality-exception: {waived_total}")
        if inventory_total is not None:
            lines.append(f"- Runtime-boundary annotations: {inventory_total}")
        if subtree_bits:
            lines.append(f"- Top annotation subtrees: {', '.join(subtree_bits)}")
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
        middleman_candidate_count, unreferenced_candidate_count = file_size_structure_candidate_counts(file_size)
        files = file_size.get("files", [])
        import_blocks = file_size.get("import_blocks", [])
        flat_directories = file_size.get("flat_directories", [])
        delegation_candidates = file_size.get("delegation_candidates", [])
        middleman_modules = file_size.get("middleman_modules", [])
        unreferenced_files = file_size.get("unreferenced_files", [])

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
        lines.append(f"- Middle-man modules: {middleman_candidate_count}")
        lines.append(f"- Unreferenced file candidates: {unreferenced_candidate_count}")
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
        if isinstance(middleman_modules, list) and middleman_modules:
            first = middleman_modules[0]
            if isinstance(first, dict):
                lines.append(f"- Top middle-man module: {first.get('path')} (exports={first.get('exports')})")
        if isinstance(unreferenced_files, list) and unreferenced_files:
            first = unreferenced_files[0]
            if isinstance(first, dict):
                lines.append(f"- Top dead-file candidate: {first.get('path')} ({first.get('lines')} lines)")
        lines.append(f"- Report: {buildlog_dir / 'file-size-analysis.md'}")
        lines.append("")

    if loc_check is not None:
        loc_counts, default_counts, test_counts = loc_check_counts(loc_check)
        files = loc_check.get("files", [])
        bucket_parts = loc_bucket_parts(loc_counts, assignment=True)

        lines.append("### LOC Check")
        lines.append(f"- File buckets: {', '.join(bucket_parts) if bucket_parts else 'none'}")
        if default_counts.get("total", 0):
            lines.append(f"- Default-scope hits: {default_counts['total']}")
        if test_counts.get("total", 0):
            lines.append(f"- Test-scope hits: {test_counts['total']}")
        if isinstance(files, list) and files:
            first = files[0]
            if isinstance(first, dict):
                lines.append(
                    f"- Largest file: {first.get('path')} ({first.get('lines')} lines, {first.get('bucket')})"
                )
        lines.append(f"- Report: {buildlog_dir / 'loc-check.md'}")
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
