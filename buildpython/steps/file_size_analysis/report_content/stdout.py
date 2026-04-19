from __future__ import annotations

from typing import Any

from ..constants import DIRECT_PYTHON_FILE_THRESHOLD
from ._shared import delegation_count, file_counts, import_counts, middleman_count, unreferenced_count


def build_stdout_lines(
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
        f"Middle-man modules: {middleman_candidate_count}",
        f"Unreferenced files: {unreferenced_candidate_count}",
        f"Quality-exception waivers: {len(waiver_rows)}",
    ]

    has_hotspots = bool(
        file_rows or import_rows or flat_directories or delegation_rows or middleman_rows or unreferenced_rows
    )
    if not has_hotspots:
        lines.extend(["", "No file-size or structure hotspots detected."])
        if not flat_directories_allowed and not waiver_rows:
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
    if middleman_rows:
        lines.extend(["", "Middle-man modules:"])
        for item in middleman_rows[:20]:
            lines.append(
                "  "
                f"[exports={int(item['exports']):2d}, inbound={int(item['inbound_imports']):2d}] {item['path']} "
                f"(imports: {int(item['import_statements'])}, aliases: {int(item['alias_bindings'])})"
            )
    if unreferenced_rows:
        lines.extend(["", "Unreferenced file candidates:"])
        for item in unreferenced_rows[:20]:
            lines.append(
                "  "
                f"[{int(item['lines']):4d} lines, inbound={int(item['inbound_imports']):2d}] {item['path']} "
                f"({item['reason']})"
            )

    if waiver_rows:
        lines.extend(["", "Quality-exception waivers (`@quality-exception file-size-analysis`):"])
        for item in waiver_rows[:20]:
            lines.append(f"  [waived] {item['path']} ({item['reason']})")

    return lines