from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _coverage_status(coverage: dict[str, Any]) -> str | None:
    summary = coverage.get("summary", {})
    if not isinstance(summary, dict):
        return None
    status = summary.get("status")
    return status if isinstance(status, str) else None


def build_debt_index(buildlog_dir: Path) -> dict[str, Any]:
    hygiene = _read_json_if_exists(buildlog_dir / "code-hygiene.json")
    exception_transparency = _read_json_if_exists(buildlog_dir / "exception-transparency.json")
    markers = _read_json_if_exists(buildlog_dir / "code-markers.json")
    file_size = _read_json_if_exists(buildlog_dir / "file-size-analysis.json")
    loc_check = _read_json_if_exists(buildlog_dir / "loc-check.json")
    architecture = _read_json_if_exists(buildlog_dir / "architecture-validation.json")
    coverage = _read_json_if_exists(buildlog_dir / "coverage-summary.json")

    sections: dict[str, Any] = {}
    report_paths: dict[str, str] = {}

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
            "facade_candidates": file_size.get("facade_candidates", []),
        }
        report_paths["file_size"] = str(buildlog_dir / "file-size-analysis.md")

    if loc_check is not None:
        sections["loc_check"] = {
            "threshold": loc_check.get("threshold"),
            "count": loc_check.get("count"),
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
            "available_sections": sorted(sections.keys()),
            "report_count": len(report_paths),
        },
        "reports": report_paths,
        "sections": sections,
    }


def write_debt_index(buildlog_dir: Path) -> None:
    buildlog_dir.mkdir(parents=True, exist_ok=True)
    payload = build_debt_index(buildlog_dir)

    json_path = buildlog_dir / "debt-index.json"
    md_path = buildlog_dir / "debt-index.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines: list[str] = [
        "# Debt index",
        "",
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
            lines.extend(["## Exception transparency", ""])
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
            facade_candidates = file_size.get("facade_candidates", [])
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
            lines.append(f"- Facade candidates: {len(facade_candidates) if isinstance(facade_candidates, list) else 0}")
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
            if isinstance(facade_candidates, list) and facade_candidates:
                first = facade_candidates[0]
                if isinstance(first, dict):
                    lines.append(f"- Top facade candidate: {first.get('path')} (score={first.get('score')})")
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
