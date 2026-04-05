from __future__ import annotations

from typing import Any

from pathlib import Path

from ..reports import write_csv, write_json, write_md
from .constants import (
    CRITICAL_LINES,
    DIRECTORY_SCAN_ROOTS,
    DIRECT_PYTHON_FILE_THRESHOLD,
    EXTREME_LINES,
    IMPORT_BLOCK_CRITICAL_LINES,
    IMPORT_BLOCK_SEVERE_LINES,
    IMPORT_BLOCK_WARNING_LINES,
    REFACTOR_LINES,
    SEVERE_LINES,
    SIZE_SCAN_ROOTS,
)


def file_counts(file_rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "refactor": sum(1 for item in file_rows if item["bucket"] == "REFACTOR"),
        "critical": sum(1 for item in file_rows if item["bucket"] == "CRITICAL"),
        "severe": sum(1 for item in file_rows if item["bucket"] == "SEVERE"),
        "extreme": sum(1 for item in file_rows if item["bucket"] == "EXTREME"),
        "total": len(file_rows),
    }


def import_counts(import_rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "warning": sum(1 for item in import_rows if item["level"] == "WARNING"),
        "critical": sum(1 for item in import_rows if item["level"] == "CRITICAL"),
        "severe": sum(1 for item in import_rows if item["level"] == "SEVERE"),
        "total": len(import_rows),
    }


def delegation_count(delegation_rows: list[dict[str, Any]]) -> int:
    return len(delegation_rows)


def build_stdout_lines(
    *,
    file_rows: list[dict[str, Any]],
    import_rows: list[dict[str, Any]],
    flat_directories: list[dict[str, Any]],
    flat_directories_allowed: list[dict[str, Any]],
    delegation_rows: list[dict[str, Any]],
) -> list[str]:
    file_size_counts = file_counts(file_rows)
    import_block_counts = import_counts(import_rows)
    delegation_candidate_count = delegation_count(delegation_rows)

    lines: list[str] = [
        "File size analysis",
        "",
        "File-size ranges: refactor=350-399, critical=400-499, severe=500-599, extreme=600+",
        "Import-block ranges: warning=20-29, critical=30-39, severe=40+",
        f"Flat-directory threshold: >={DIRECT_PYTHON_FILE_THRESHOLD} direct Python files",
        "Delegation candidates: import block >=20 lines plus many alias bindings/delegating wrappers",
        "",
        (
            "Large files: "
            f"Refactor={file_size_counts['refactor']} | Critical={file_size_counts['critical']} | "
            f"Severe={file_size_counts['severe']} | Extreme={file_size_counts['extreme']}"
        ),
        (
            "Import blocks: "
            f"Warning={import_block_counts['warning']} | Critical={import_block_counts['critical']} | "
            f"Severe={import_block_counts['severe']}"
        ),
        f"Flat directories: {len(flat_directories)}",
        f"Flat directories (suppressed by allowlist): {len(flat_directories_allowed)}",
        f"Delegation candidates: {delegation_candidate_count}",
    ]

    has_hotspots = bool(file_rows or import_rows or flat_directories or delegation_rows)
    if not has_hotspots:
        lines.extend(["", "No file-size or structure hotspots detected."])
        if not flat_directories_allowed:
            return lines

    if file_rows:
        lines.extend(["", "Largest files:"])
        for item in file_rows[:25]:
            lines.append(f"  [{item['bucket']}] {int(item['lines']):4d}  {item['path']}")

    if import_rows:
        lines.extend(["", "Longest import blocks:"])
        for item in import_rows[:20]:
            lines.append(
                f"  [{item['level']}] {int(item['lines']):4d} lines / {int(item['statements']):2d} stmts  {item['path']}"
            )

    if flat_directories:
        lines.extend(["", "Flat directories:"])
        for item in flat_directories[:20]:
            lines.append(
                "  "
                f"[{int(item['direct_python_files']):2d} files, density={float(item['flatness_density']):.1f}] "
                f"{item['path']} (subdirs: {int(item['subdirectories'])})"
            )
    if flat_directories_allowed:
        lines.extend(["", "Flat directories (suppressed by allowlist):"])
        for item in flat_directories_allowed:
            lines.append(f"  [allowed] {item['path']} — {item.get('allowed_reason', '')}")
    if delegation_rows:
        lines.extend(["", "Delegation candidates:"])
        for item in delegation_rows[:20]:
            lines.append(
                "  "
                f"[score={int(item['score']):2d}] {item['path']} "
                f"(imports: {int(item['import_lines'])} lines, aliases: {int(item['alias_bindings'])}, "
                f"delegates: {int(item['delegating_callables'])})"
            )

    return lines


def write_reports(
    *,
    root: Path,
    file_rows: list[dict[str, Any]],
    import_rows: list[dict[str, Any]],
    flat_directories: list[dict[str, Any]],
    flat_directories_allowed: list[dict[str, Any]],
    delegation_rows: list[dict[str, Any]],
) -> None:
    report_dir = root / "buildlog" / "keyrgb"
    report_json = report_dir / "file-size-analysis.json"
    report_csv = report_dir / "file-size-analysis.csv"
    report_md = report_dir / "file-size-analysis.md"
    file_size_counts = file_counts(file_rows)
    import_block_counts = import_counts(import_rows)
    delegation_candidate_count = delegation_count(delegation_rows)

    write_json(
        report_json,
        {
            "thresholds": {
                "file_lines": {
                    "refactor": {"min": REFACTOR_LINES, "max": CRITICAL_LINES - 1},
                    "critical": {"min": CRITICAL_LINES, "max": SEVERE_LINES - 1},
                    "severe": {"min": SEVERE_LINES, "max": EXTREME_LINES - 1},
                    "extreme": {"min": EXTREME_LINES},
                },
                "import_block_lines": {
                    "warning": {"min": IMPORT_BLOCK_WARNING_LINES, "max": IMPORT_BLOCK_CRITICAL_LINES - 1},
                    "critical": {"min": IMPORT_BLOCK_CRITICAL_LINES, "max": IMPORT_BLOCK_SEVERE_LINES - 1},
                    "severe": {"min": IMPORT_BLOCK_SEVERE_LINES},
                },
                "flat_directories": {
                    "direct_python_files_min": DIRECT_PYTHON_FILE_THRESHOLD,
                },
                "delegation_candidates": {
                    "import_block_lines_min": 20,
                    "alias_bindings_min": 4,
                    "delegating_callables_min": 6,
                    "score_min": 10,
                },
            },
            "scopes": {
                "file_analysis_roots": list(SIZE_SCAN_ROOTS),
                "flat_directory_roots": list(DIRECTORY_SCAN_ROOTS),
            },
            "counts": {
                "file_lines": file_size_counts,
                "import_block_lines": import_block_counts,
                "flat_directories": len(flat_directories),
                "flat_directories_allowed": len(flat_directories_allowed),
                "delegation_candidates": delegation_candidate_count,
            },
            "files": file_rows,
            "import_blocks": import_rows,
            "flat_directories": flat_directories,
            "flat_directories_allowed": flat_directories_allowed,
            "delegation_candidates": delegation_rows,
        },
    )

    write_csv(
        report_csv,
        ["section", "primary", "secondary", "level", "path", "details"],
        [["file", str(item["lines"]), "", str(item["bucket"]), str(item["path"]), ""] for item in file_rows]
        + [
            [
                "import_block",
                str(item["lines"]),
                str(item["statements"]),
                str(item["level"]),
                str(item["path"]),
                "",
            ]
            for item in import_rows
        ]
        + [
            [
                "flat_directory",
                str(item["direct_python_files"]),
                str(item["subdirectories"]),
                "STRUCTURE",
                str(item["path"]),
                ", ".join(str(example) for example in item["examples"]),
            ]
            for item in flat_directories
        ]
        + [
            [
                "delegation_candidate",
                str(item["score"]),
                str(item["import_lines"]),
                "DELEGATION",
                str(item["path"]),
                (
                    f"aliases={item['alias_bindings']}, delegates={item['delegating_callables']}, "
                    f"callables={item['callables']}"
                ),
            ]
            for item in delegation_rows
        ],
    )

    md_lines: list[str] = [
        "# File size analysis",
        "",
        "## Scope",
        "",
        f"- File-size roots: {', '.join(SIZE_SCAN_ROOTS)}",
        f"- Flat-directory roots: {', '.join(DIRECTORY_SCAN_ROOTS)}",
        "",
        "## Summary",
        "",
        "- File-size ranges: refactor=350-399, critical=400-499, severe=500-599, extreme=600+",
        (
            f"- Large files: refactor={file_size_counts['refactor']}, critical={file_size_counts['critical']}, "
            f"severe={file_size_counts['severe']}, extreme={file_size_counts['extreme']}"
        ),
        "- Import-block ranges: warning=20-29, critical=30-39, severe=40+",
        (
            f"- Long import blocks: warning={import_block_counts['warning']}, "
            f"critical={import_block_counts['critical']}, severe={import_block_counts['severe']}"
        ),
        f"- Flat directories (>={DIRECT_PYTHON_FILE_THRESHOLD} direct Python files): {len(flat_directories)}",
        f"- Flat directories (suppressed by allowlist): {len(flat_directories_allowed)}",
        f"- Delegation candidates: {delegation_candidate_count}",
        "",
    ]

    if file_rows:
        md_lines.extend(["## Large files", "", "| Lines | Bucket | Path |", "|---:|---|---|"])
        for item in file_rows[:200]:
            md_lines.append(f"| {item['lines']} | {item['bucket']} | {item['path']} |")
        md_lines.append("")
    else:
        md_lines.extend(["## Large files", "", "No large files detected.", ""])

    if import_rows:
        md_lines.extend(
            [
                "## Import block hotspots",
                "",
                "| Lines | Statements | Level | Path |",
                "|---:|---:|---|---|",
            ]
        )
        for item in import_rows[:200]:
            md_lines.append(f"| {item['lines']} | {item['statements']} | {item['level']} | {item['path']} |")
        md_lines.append("")
    else:
        md_lines.extend(["## Import block hotspots", "", "No long import blocks detected.", ""])

    if flat_directories:
        md_lines.extend(
            [
                "## Flat directory hotspots",
                "",
                "| Direct Python files | Subdirectories | Path | Examples |",
                "|---:|---:|---|---|",
            ]
        )
        for item in flat_directories[:100]:
            md_lines.append(
                "| "
                f"{item['direct_python_files']} | {item['subdirectories']} | {item['path']} | "
                f"{', '.join(str(example) for example in item['examples'])} |"
            )
        md_lines.append("")
    else:
        md_lines.extend(["## Flat directory hotspots", "", "No flat directories exceeded the threshold.", ""])

    if flat_directories_allowed:
        md_lines.extend(
            [
                "## Flat directories suppressed by allowlist",
                "",
                "| Direct Python files | Subdirectories | Density | Path | Reason |",
                "|---:|---:|---:|---|---|",
            ]
        )
        for item in flat_directories_allowed:
            md_lines.append(
                "| "
                f"{item['direct_python_files']} | {item['subdirectories']} | "
                f"{item['flatness_density']} | {item['path']} | "
                f"{item.get('allowed_reason', '')} |"
            )
        md_lines.append("")

    if delegation_rows:
        md_lines.extend(
            [
                "## Delegation candidates",
                "",
                "| Score | Import lines | Aliases | Delegates | Callables | Path |",
                "|---:|---:|---:|---:|---:|---|",
            ]
        )
        for item in delegation_rows[:100]:
            md_lines.append(
                f"| {item['score']} | {item['import_lines']} | {item['alias_bindings']} | "
                f"{item['delegating_callables']} | {item['callables']} | {item['path']} |"
            )
        md_lines.append("")
    else:
        md_lines.extend(["## Delegation candidates", "", "No delegation candidates exceeded the threshold.", ""])

    write_md(report_md, md_lines)
