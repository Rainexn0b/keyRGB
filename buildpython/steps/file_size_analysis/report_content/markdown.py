from __future__ import annotations

from typing import Any

from ..constants import DIRECTORY_SCAN_ROOTS, DIRECT_PYTHON_FILE_THRESHOLD, SIZE_SCAN_ROOTS
from ._shared import delegation_count, file_counts, import_counts, middleman_count, unreferenced_count


def build_markdown_lines(
    *,
    file_rows: list[dict[str, Any]],
    import_rows: list[dict[str, Any]],
    flat_directories: list[dict[str, Any]],
    flat_directories_allowed: list[dict[str, Any]],
    delegation_rows: list[dict[str, Any]],
    middleman_rows: list[dict[str, Any]],
    unreferenced_rows: list[dict[str, Any]],
    waiver_rows: list[dict[str, str]],
) -> list[str]:
    file_size_counts = file_counts(file_rows)
    import_block_counts = import_counts(import_rows)
    delegation_candidate_count = delegation_count(delegation_rows)
    middleman_candidate_count = middleman_count(middleman_rows)
    unreferenced_candidate_count = unreferenced_count(unreferenced_rows)

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
        f"- Middle-man modules: {middleman_candidate_count}",
        f"- Unreferenced file candidates: {unreferenced_candidate_count}",
        f"- Quality-exception waivers (`@quality-exception file-size-analysis`): {len(waiver_rows)}",
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

    if middleman_rows:
        md_lines.extend(
            [
                "## Middle-man modules",
                "",
                "| Exports | Inbound imports | Import statements | Alias bindings | Path |",
                "|---:|---:|---:|---:|---|",
            ]
        )
        for item in middleman_rows[:100]:
            md_lines.append(
                f"| {item['exports']} | {item['inbound_imports']} | {item['import_statements']} | "
                f"{item['alias_bindings']} | {item['path']} |"
            )
        md_lines.append("")
    else:
        md_lines.extend(["## Middle-man modules", "", "No middle-man modules detected.", ""])

    if unreferenced_rows:
        md_lines.extend(
            [
                "## Unreferenced file candidates",
                "",
                "| Lines | Inbound imports | Path | Reason |",
                "|---:|---:|---|---|",
            ]
        )
        for item in unreferenced_rows[:100]:
            md_lines.append(
                f"| {item['lines']} | {item['inbound_imports']} | {item['path']} | {item['reason']} |"
            )
        md_lines.append("")
    else:
        md_lines.extend(["## Unreferenced file candidates", "", "No unreferenced file candidates detected.", ""])

    if waiver_rows:
        md_lines.extend(
            [
                "## Quality-exception waivers",
                "",
                "| Path | Reason |",
                "|---|---|",
            ]
        )
        for item in waiver_rows:
            md_lines.append(f"| {item['path']} | {item['reason']} |")
        md_lines.append("")

    return md_lines