from __future__ import annotations

from typing import Any

import ast
import json
from pathlib import Path

from . import _ast_scan_helpers as _scan_helpers
from . import constants as _constants
from . import usage_graph as _usage_graph
from ..quality_exceptions import explanation_for_quality_exception_step

delegation_candidate_metrics = _scan_helpers.delegation_candidate_metrics
import_block_metrics = _scan_helpers.import_block_metrics
load_module_scan_context = _scan_helpers.load_module_scan_context
middleman_candidate_metrics = _scan_helpers.middleman_candidate_metrics
_module_docstring_consumes_first_statement = _scan_helpers.module_docstring_consumes_first_statement

DIRECTORY_SCAN_ROOTS = _constants.DIRECTORY_SCAN_ROOTS
DIRECT_PYTHON_FILE_THRESHOLD = _constants.DIRECT_PYTHON_FILE_THRESHOLD
file_bucket = _constants.file_bucket
import_block_level = _constants.import_block_level

build_usage_graph = _usage_graph.build_usage_graph
inbound_import_count = _usage_graph.inbound_import_count

_FLAT_DIRECTORY_ALLOWLIST_PATH = Path("buildpython/config/debt_baselines.json")
_QUALITY_EXCEPTION_STEP_SLUG = "file-size-analysis"


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


def _comment_text(line: str) -> str | None:
    comment_index = line.find("#")
    if comment_index == -1:
        return None
    return line[comment_index + 1 :].strip()


def file_size_quality_exception_reason(lines: list[str]) -> str | None:
    for line in lines:
        explanation = explanation_for_quality_exception_step(
            _comment_text(line),
            step_slug=_QUALITY_EXCEPTION_STEP_SLUG,
        )
        if explanation:
            return explanation
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


def scan_middleman_candidate(path: Path) -> dict[str, Any] | None:
    context = load_module_scan_context(path)
    if context is None:
        return None
    return middleman_candidate_metrics(context)


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
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, str]],
]:
    file_rows: list[dict[str, Any]] = []
    import_rows: list[dict[str, Any]] = []
    delegation_rows: list[dict[str, Any]] = []
    middleman_rows: list[dict[str, Any]] = []
    waived_rows: list[dict[str, str]] = []
    waived_paths: set[str] = set()
    usage_graph = build_usage_graph(root, roots=roots)

    for path in iter_py_files(root, roots=roots):
        lines = read_lines(path)
        if lines is None:
            continue

        line_count = len(lines)
        bucket = file_bucket(line_count)
        rel = str(path.relative_to(root))
        waiver_reason = file_size_quality_exception_reason(lines)
        if waiver_reason is not None:
            waived_paths.add(rel)
            waived_rows.append({"path": rel, "reason": waiver_reason})
            continue

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

        middleman_candidate = scan_middleman_candidate(path)
        if middleman_candidate is not None:
            inbound_count = inbound_import_count(usage_graph, path)
            if inbound_count and (not usage_graph.root_paths or path in usage_graph.reachable):
                middleman_candidate["path"] = rel
                middleman_candidate["inbound_imports"] = inbound_count
                middleman_rows.append(middleman_candidate)

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
    middleman_rows.sort(
        key=lambda item: (
            -int(item["inbound_imports"]),
            -int(item["exports"]),
            -int(item["import_statements"]),
            str(item["path"]),
        )
    )
    flat_directories, flat_directories_allowed = scan_flat_directories(root)
    unreferenced_rows = scan_unreferenced_file_candidates(
        root,
        roots=roots,
        usage_graph=usage_graph,
        waived_paths=waived_paths,
    )
    waived_rows.sort(key=lambda item: str(item["path"]))
    return (
        file_rows,
        import_rows,
        flat_directories,
        flat_directories_allowed,
        delegation_rows,
        middleman_rows,
        unreferenced_rows,
        waived_rows,
    )


def scan_unreferenced_file_candidates(
    root: Path,
    *,
    roots: tuple[str, ...],
    usage_graph: Any | None = None,
    waived_paths: set[str] | None = None,
) -> list[dict[str, Any]]:
    graph = usage_graph if usage_graph is not None else build_usage_graph(root, roots=roots)
    if not graph.root_paths:
        return []

    waived = waived_paths or set()
    rows: list[dict[str, Any]] = []
    for path in iter_py_files(root, roots=roots):
        rel = str(path.relative_to(root))
        if path.name == "__init__.py" or path in graph.reachable or rel in waived:
            continue
        lines = read_lines(path)
        if lines is None:
            continue
        inbound_count = inbound_import_count(graph, path)
        reason = "Not reachable from configured entrypoints"
        if inbound_count:
            reason += f" ({inbound_count} inbound import{'s' if inbound_count != 1 else ''})"
        rows.append(
            {
                "path": rel,
                "lines": len(lines),
                "inbound_imports": inbound_count,
                "reason": reason,
            }
        )

    rows.sort(key=lambda item: (-int(item["lines"]), -int(item["inbound_imports"]), str(item["path"])))
    return rows
