from __future__ import annotations


REFACTOR_LINES = 350
CRITICAL_LINES = 400
SEVERE_LINES = 500
EXTREME_LINES = 600

IMPORT_BLOCK_WARNING_LINES = 20
IMPORT_BLOCK_CRITICAL_LINES = 30
IMPORT_BLOCK_SEVERE_LINES = 40

DIRECT_PYTHON_FILE_THRESHOLD = 8

DELEGATION_IMPORT_BLOCK_MIN_LINES = 20
DELEGATION_ALIAS_BINDINGS_MIN = 4
DELEGATION_DELEGATING_CALLABLES_MIN = 6
DELEGATION_SCORE_MIN = 10

SIZE_SCAN_ROOTS = ("src", "buildpython")
DIRECTORY_SCAN_ROOTS = ("src", "buildpython", "tests")


def file_bucket(line_count: int) -> str | None:
    if line_count >= EXTREME_LINES:
        return "EXTREME"
    if line_count >= SEVERE_LINES:
        return "SEVERE"
    if line_count >= CRITICAL_LINES:
        return "CRITICAL"
    if line_count >= REFACTOR_LINES:
        return "REFACTOR"
    return None


def import_block_level(line_count: int) -> str | None:
    if line_count >= IMPORT_BLOCK_SEVERE_LINES:
        return "SEVERE"
    if line_count >= IMPORT_BLOCK_CRITICAL_LINES:
        return "CRITICAL"
    if line_count >= IMPORT_BLOCK_WARNING_LINES:
        return "WARNING"
    return None
