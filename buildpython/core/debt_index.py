from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .summary_support.common import loc_bucket_parts, loc_check_counts, loc_severe_scope_part, read_json_if_exists


def _coverage_status(coverage: dict[str, Any]) -> str | None:
    summary = coverage.get("summary", {})
    if not isinstance(summary, dict):
        return None
    status = summary.get("status")
    return status if isinstance(status, str) else None


def _annotation_inventory_summary(payload: dict[str, Any]) -> tuple[int | None, list[str]]:
    annotation_inventory = payload.get("annotation_inventory", {})
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


def build_debt_index(buildlog_dir: Path, *, report_names: tuple[str, ...] | None = None) -> dict[str, Any]:
    hygiene = read_json_if_exists(buildlog_dir / "code-hygiene.json", report_names=report_names)
    exception_transparency = read_json_if_exists(
        buildlog_dir / "exception-transparency.json", report_names=report_names
    )
    markers = read_json_if_exists(buildlog_dir / "code-markers.json", report_names=report_names)
    file_size = read_json_if_exists(buildlog_dir / "file-size-analysis.json", report_names=report_names)
    loc_check = read_json_if_exists(buildlog_dir / "loc-check.json", report_names=report_names)
    architecture = read_json_if_exists(buildlog_dir / "architecture-validation.json", report_names=report_names)
    coverage = read_json_if_exists(buildlog_dir / "coverage-summary.json", report_names=report_names)
    dead_code = read_json_if_exists(buildlog_dir / "dead-code-vulture.json", report_names=report_names)

    sections: dict[str, Any] = {}
    report_paths: dict[str, str] = {}

    if dead_code is not None:
        sections["dead_code"] = {"candidates": dead_code.get("count"), "actionable": dead_code.get("actionable_count")}
        report_paths["dead_code"] = str(buildlog_dir / "dead-code-vulture.md")

    if hygiene is not None:
        sections["code_hygiene"] = {
            "active_counts": hygiene.get("active_counts", {}),
            "suppressed_counts": hygiene.get("suppressed_counts", {}),
            "top_files_by_category": hygiene.get("top_files_by_category", {}),
        }
        report_paths["code_hygiene"] = str(buildlog_dir / "code-hygiene.md")

    if exception_transparency is not None:
        sections["exception_transparency"] = {
            "counts": exception_transparency.get("counts", {}),
            "waived_total": exception_transparency.get("waived_total", 0),
            "annotation_inventory": exception_transparency.get("annotation_inventory", {}),
            "top_files_by_category": exception_transparency.get("top_files_by_category", {}),
        }
        report_paths["exception_transparency"] = str(buildlog_dir / "exception-transparency.md")

    if markers is not None:
        sections["code_markers"] = {
            "marker_counts": markers.get("marker_counts", {}),
            "regressions": markers.get("baseline", {}).get("regressions", []),
            "top_marker_files": markers.get("top_marker_files", {}),
        }
        report_paths["code_markers"] = str(buildlog_dir / "code-markers.md")

    if file_size is not None:
        sections["file_size"] = {
            "counts": file_size.get("counts", {}),
            "files": file_size.get("files", []),
            "import_blocks": file_size.get("import_blocks", []),
            "flat_directories": file_size.get("flat_directories", []),
            "delegation_candidates": file_size.get("delegation_candidates", []),
            "middleman_modules": file_size.get("middleman_modules", []),
            "unreferenced_files": file_size.get("unreferenced_files", []),
        }
        report_paths["file_size"] = str(buildlog_dir / "file-size-analysis.md")

    if loc_check is not None:
        sections["loc_check"] = {
            "threshold": loc_check.get("threshold"),
            "thresholds": loc_check.get("thresholds"),
            "count": loc_check.get("count"),
            "counts": loc_check.get("counts", {}),
            "counts_by_scope": loc_check.get("counts_by_scope", {}),
            "files": loc_check.get("files", []),
        }
        report_paths["loc_check"] = str(buildlog_dir / "loc-check.md")

    if architecture is not None:
        sections["architecture_validation"] = architecture.get("summary", {})
        report_paths["architecture_validation"] = str(buildlog_dir / "architecture-validation.md")

    if coverage is not None:
        sections["coverage"] = {
            "summary": coverage.get("summary", {}),
            "regressions": coverage.get("baseline", {}).get("regressions", []),
            "tracked_prefixes": coverage.get("tracked_prefixes", []),
            "watch_files": coverage.get("watch_files", []),
        }
        report_paths["coverage"] = str(buildlog_dir / "coverage-summary.md")

    return {
        "summary": {
            "scope": "current_run" if report_names is not None else "latest_available",
            "available_sections": sorted(sections.keys()),
            "report_count": len(report_paths),
        },
        "reports": report_paths,
        "sections": sections,
    }


def write_debt_index(buildlog_dir: Path, *, report_names: tuple[str, ...] | None = None) -> None:
    buildlog_dir.mkdir(parents=True, exist_ok=True)
    payload = build_debt_index(buildlog_dir, report_names=report_names)

    json_path = buildlog_dir / "debt-index.json"
    md_path = buildlog_dir / "debt-index.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines: list[str] = [
        "# Debt index",
        "",
        f"- Scope: {payload['summary']['scope']}",
        f"- Reports: {payload.get('summary', {}).get('report_count', 0)}",
        f"- Sections: {', '.join(payload.get('summary', {}).get('available_sections', [])) or 'none'}",
        "",
    ]

    reports = payload.get("reports", {})
    if isinstance(reports, dict) and reports:
        lines.extend(["## Reports", ""])
        for name, path in sorted(reports.items()):
            lines.append(f"- {name}: {path}")
        lines.append("")

    sections = payload.get("sections", {})
    if isinstance(sections, dict):
        dead_code = sections.get("dead_code")
        if isinstance(dead_code, dict):
            lines.extend(
                [
                    "## Dead code",
                    "",
                    f"- Candidates: {dead_code.get('candidates')}",
                    f"- Actionable findings: {dead_code.get('actionable')}",
                    "",
                ]
            )
        hygiene = sections.get("code_hygiene")
        if isinstance(hygiene, dict):
            active = hygiene.get("active_counts", {})
            suppressed = hygiene.get("suppressed_counts", {})
            lines.extend(["## Code hygiene", ""])
            for category in [
                "silent_broad_except",
                "logged_broad_except",
                "fallback_broad_except",
                "cleanup_hotspot",
                "forbidden_getattr",
            ]:
                value = active.get(category)
                if isinstance(value, int):
                    s = suppressed.get(category, 0)
                    supp_text = f" (suppressed {s})" if isinstance(s, int) and s else ""
                    lines.append(f"- {category}: {value}{supp_text}")
            lines.append("")

        exception_transparency = sections.get("exception_transparency")
        if isinstance(exception_transparency, dict):
            counts = exception_transparency.get("counts", {})
            waived_total = exception_transparency.get("waived_total", 0)
            inventory_total, subtree_bits = _annotation_inventory_summary(exception_transparency)
            lines.extend(["## Exception transparency", ""])
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
                value = counts.get(category)
                if isinstance(value, int):
                    lines.append(f"- {category}: {value}")
            lines.append("")

        file_size = sections.get("file_size")
        if isinstance(file_size, dict):
            counts = file_size.get("counts", {})
            file_counts = counts.get("file_lines", counts) if isinstance(counts, dict) else {}
            import_counts = counts.get("import_block_lines", {}) if isinstance(counts, dict) else {}
            files = file_size.get("files", [])
            import_blocks = file_size.get("import_blocks", [])
            flat_directories = file_size.get("flat_directories", [])
            delegation_candidates = file_size.get("delegation_candidates", [])
            middleman_modules = file_size.get("middleman_modules", [])
            unreferenced_files = file_size.get("unreferenced_files", [])
            lines.extend(["## File size", ""])
            if isinstance(file_counts, dict):
                lines.append(
                    "- File buckets: "
                    f"refactor={file_counts.get('refactor', 0)}, "
                    f"critical={file_counts.get('critical', 0)}, "
                    f"severe={file_counts.get('severe', 0)}, "
                    f"extreme={file_counts.get('extreme', 0)}"
                )
            if isinstance(import_counts, dict):
                lines.append(
                    "- Import blocks: "
                    f"warning={import_counts.get('warning', 0)}, "
                    f"critical={import_counts.get('critical', 0)}, "
                    f"severe={import_counts.get('severe', 0)}"
                )
            lines.append(f"- Flat directories: {len(flat_directories) if isinstance(flat_directories, list) else 0}")
            lines.append(
                f"- Delegation candidates: {len(delegation_candidates) if isinstance(delegation_candidates, list) else 0}"
            )
            lines.append(
                f"- Middle-man modules: {len(middleman_modules) if isinstance(middleman_modules, list) else 0}"
            )
            lines.append(
                f"- Unreferenced file candidates: {len(unreferenced_files) if isinstance(unreferenced_files, list) else 0}"
            )
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
            lines.append("")

        loc_check = sections.get("loc_check")
        if isinstance(loc_check, dict):
            loc_counts, default_counts, test_counts = loc_check_counts(loc_check)
            files = loc_check.get("files", [])
            bucket_parts = loc_bucket_parts({**loc_counts, "severe": 0}, assignment=True)
            severe_part = loc_severe_scope_part(default_counts, test_counts, assignment=True)
            if severe_part is not None:
                bucket_parts.append(severe_part)
            lines.extend(["## LOC check", ""])
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
            lines.append("")

        coverage = sections.get("coverage")
        if isinstance(coverage, dict):
            summary = coverage.get("summary", {})
            regressions = coverage.get("regressions", [])
            lines.extend(["## Coverage", ""])
            if _coverage_status({"summary": summary}) == "missing_capture":
                lines.append("- Status: waiting for pytest coverage capture")
                lines.append("- Run: .venv/bin/python -m buildpython --run-steps=2,18")
            else:
                lines.append(f"- Total coverage: {summary.get('total_percent', 0.0)}%")
                if isinstance(regressions, list) and regressions:
                    lines.append("- Regressions:")
                    for item in regressions[:10]:
                        if not isinstance(item, dict):
                            continue
                        lines.append(
                            f"  - {item.get('kind')} {item.get('target')}: {item.get('current')} < {item.get('baseline')}"
                        )
                else:
                    lines.append("- Regressions: none")
            lines.append("")

        architecture = sections.get("architecture_validation")
        if isinstance(architecture, dict):
            lines.extend(["## Architecture validation", ""])
            lines.append(f"- Findings: {architecture.get('findings', 0)}")
            lines.append(f"- Errors: {architecture.get('errors', 0)}")
            lines.append(f"- Warnings: {architecture.get('warnings', 0)}")
            lines.append("")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
