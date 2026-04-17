from __future__ import annotations

from typing import Any

import ast
import json
from pathlib import Path

from ._ast_scan_helpers import (
    delegation_candidate_metrics,
    import_block_metrics,
    load_module_scan_context,
    module_docstring_consumes_first_statement as _module_docstring_consumes_first_statement,
)
from .constants import (
    DIRECTORY_SCAN_ROOTS,
    DIRECT_PYTHON_FILE_THRESHOLD,
    file_bucket,
    import_block_level,
)

_FLAT_DIRECTORY_ALLOWLIST_PATH = Path("buildpython/config/debt_baselines.json")


def load_flat_directory_allowlist(root: Path) -> dict[str, str]:
    """Return {repo-relative-path: reason} for directories exempt from the flat-directory check.

    Reads from the ``flat_directories.allowed`` section of the shared debt-baselines config.
    Returns an empty dict on any read/parse failure (fail-open).
    """
    config_path = root / _FLAT_DIRECTORY_ALLOWLIST_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    entries = payload.get("flat_directories", {}).get("allowed", [])
    if not isinstance(entries, list):
        return {}

    allowlist: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        path_val = entry.get("path")
        reason_val = entry.get("reason", "")
        if isinstance(path_val, str) and path_val:
            # Normalise separators so entries always use forward slashes.
            allowlist[path_val.replace("\\", "/")] = str(reason_val)
    return allowlist


def iter_py_files(root: Path, *, roots: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for folder_name in roots:
        folder = root / folder_name
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    return sorted(files)


def read_lines(path: Path) -> list[str] | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None


def module_docstring_consumes_first_statement(tree: ast.Module) -> bool:
    return _module_docstring_consumes_first_statement(tree)


def scan_import_block(path: Path) -> tuple[int, int] | None:
    context = load_module_scan_context(path)
    if context is None:
        return None
    return import_block_metrics(context)


def scan_delegation_candidate(path: Path) -> dict[str, Any] | None:
    context = load_module_scan_context(path)
    if context is None:
        return None
    return delegation_candidate_metrics(context)


def scan_flat_directories(
    root: Path,
    *,
    allowlist: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (hotspots, allowed_entries).

    hotspots — directories that exceed the threshold and are NOT in the allowlist.
    allowed_entries — directories that would have fired but are suppressed by a
    ``flat_directories.allowed`` entry in debt_baselines.json.  They are included
    in the report for auditability.
    """
    flat_directory_allowlist = allowlist if allowlist is not None else load_flat_directory_allowlist(root)
    hits: list[dict[str, Any]] = []
    allowed_entries: list[dict[str, Any]] = []
    for folder_name in DIRECTORY_SCAN_ROOTS:
        folder = root / folder_name
        if not folder.exists():
            continue
        directories = [folder, *[path for path in folder.rglob("*") if path.is_dir()]]
        for directory in sorted(directories):
            if "__pycache__" in directory.parts:
                continue
            try:
                children = list(directory.iterdir())
            except OSError:
                continue
            direct_python_files = sorted(child.name for child in children if child.is_file() and child.suffix == ".py")
            if len(direct_python_files) < DIRECT_PYTHON_FILE_THRESHOLD:
                continue
            subdirectories = sorted(child.name for child in children if child.is_dir() and child.name != "__pycache__")
            subdir_count = len(subdirectories)
            # Density = files per «slot» (1 + subdirs). A directory with many files
            # and zero subdirectories has the maximum density and is the true dumping
            # ground. A well-organised directory with many subdirectories has low
            # density and sorts much further down the list.
            density = round(len(direct_python_files) / (1 + subdir_count), 1)
            entry: dict[str, Any] = {
                "path": str(directory.relative_to(root)),
                "direct_python_files": len(direct_python_files),
                "subdirectories": subdir_count,
                "flatness_density": density,
                "examples": direct_python_files[:5],
            }
            rel_path = str(directory.relative_to(root)).replace("\\", "/")
            if rel_path in flat_directory_allowlist:
                entry["allowed_reason"] = flat_directory_allowlist[rel_path]
                allowed_entries.append(entry)
            else:
                hits.append(entry)

    # Sort by density descending (dumping grounds first) then file count as tiebreaker.
    hits.sort(key=lambda item: (-float(item["flatness_density"]), -int(item["direct_python_files"]), str(item["path"])))
    allowed_entries.sort(key=lambda item: str(item["path"]))
    return hits, allowed_entries


def collect_hotspots(
    root: Path,
    *,
    roots: tuple[str, ...],
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    file_rows: list[dict[str, Any]] = []
    import_rows: list[dict[str, Any]] = []
    delegation_rows: list[dict[str, Any]] = []

    for path in iter_py_files(root, roots=roots):
        lines = read_lines(path)
        if lines is None:
            continue

        line_count = len(lines)
        bucket = file_bucket(line_count)
        rel = str(path.relative_to(root))
        if bucket is not None:
            file_rows.append({"lines": line_count, "bucket": bucket, "path": rel})

        import_block = scan_import_block(path)
        if import_block is not None:
            import_lines, statement_count = import_block
            level = import_block_level(import_lines)
            if level is not None:
                import_rows.append(
                    {
                        "lines": import_lines,
                        "statements": statement_count,
                        "level": level,
                        "path": rel,
                    }
                )

        delegation_candidate = scan_delegation_candidate(path)
        if delegation_candidate is not None:
            delegation_candidate["path"] = rel
            delegation_rows.append(delegation_candidate)

    file_rows.sort(key=lambda item: (-int(item["lines"]), str(item["path"])))
    import_rows.sort(key=lambda item: (-int(item["lines"]), -int(item["statements"]), str(item["path"])))
    delegation_rows.sort(
        key=lambda item: (
            -int(item["score"]),
            -int(item["import_lines"]),
            -int(item["delegating_callables"]),
            str(item["path"]),
        )
    )
    flat_directories, flat_directories_allowed = scan_flat_directories(root)
    return file_rows, import_rows, flat_directories, flat_directories_allowed, delegation_rows
