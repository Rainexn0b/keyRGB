from __future__ import annotations

from typing import Any

from ..constants import (
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
from ._shared import delegation_count, file_counts, import_counts, middleman_count, unreferenced_count


def build_json_payload(
    *,
    file_rows: list[dict[str, Any]],
    import_rows: list[dict[str, Any]],
    flat_directories: list[dict[str, Any]],
    flat_directories_allowed: list[dict[str, Any]],
    delegation_rows: list[dict[str, Any]],
    middleman_rows: list[dict[str, Any]],
    unreferenced_rows: list[dict[str, Any]],
    waiver_rows: list[dict[str, str]],
) -> dict[str, Any]:
    file_size_counts = file_counts(file_rows)
    import_block_counts = import_counts(import_rows)
    delegation_candidate_count = delegation_count(delegation_rows)
    middleman_candidate_count = middleman_count(middleman_rows)
    unreferenced_candidate_count = unreferenced_count(unreferenced_rows)

    return {
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
            "middleman_modules": {
                "shape": "non-__init__ import/export facade with no local logic",
                "inbound_imports_min": 1,
            },
            "unreferenced_files": {
                "shape": "not reachable from configured entrypoints or __main__ modules",
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
            "middleman_modules": middleman_candidate_count,
            "unreferenced_files": unreferenced_candidate_count,
            "waived_files": len(waiver_rows),
        },
        "waivers": {
            "step_slug": "file-size-analysis",
            "files_total": len(waiver_rows),
            "files": waiver_rows,
        },
        "files": file_rows,
        "import_blocks": import_rows,
        "flat_directories": flat_directories,
        "flat_directories_allowed": flat_directories_allowed,
        "delegation_candidates": delegation_rows,
        "middleman_modules": middleman_rows,
        "unreferenced_files": unreferenced_rows,
    }