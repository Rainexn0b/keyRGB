from __future__ import annotations

from typing import Any

import ast
import json
from pathlib import Path

from .constants import (
    DIRECTORY_SCAN_ROOTS,
    DIRECT_PYTHON_FILE_THRESHOLD,
    DELEGATION_ALIAS_BINDINGS_MIN,
    DELEGATION_DELEGATING_CALLABLES_MIN,
    DELEGATION_IMPORT_BLOCK_MIN_LINES,
    DELEGATION_SCORE_MIN,
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
    if not tree.body:
        return False
    first = tree.body[0]
    if not isinstance(first, ast.Expr):
        return False
    value = first.value
    return isinstance(value, ast.Constant) and isinstance(value.value, str)


def scan_import_block(path: Path) -> tuple[int, int] | None:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return None

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    start_index = 1 if module_docstring_consumes_first_statement(tree) else 0
    import_nodes: list[ast.Import | ast.ImportFrom] = []
    for node in tree.body[start_index:]:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_nodes.append(node)
            continue
        break

    if not import_nodes:
        return None

    first = import_nodes[0]
    last = import_nodes[-1]
    return ((last.end_lineno or last.lineno) - first.lineno + 1, len(import_nodes))


def _leading_import_nodes(tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
    start_index = 1 if module_docstring_consumes_first_statement(tree) else 0
    import_nodes: list[ast.Import | ast.ImportFrom] = []
    for node in tree.body[start_index:]:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_nodes.append(node)
            continue
        break
    return import_nodes


def _imported_bindings(import_nodes: list[ast.Import | ast.ImportFrom]) -> set[str]:
    bindings: set[str] = set()
    for node in import_nodes:
        for alias in node.names:
            bound = alias.asname or alias.name.split(".", 1)[0]
            if bound:
                bindings.add(bound)
    return bindings


def _attribute_root_name(expr: ast.expr) -> str | None:
    current = expr
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None


def _is_import_alias_expr(expr: ast.expr | None, imported_names: set[str]) -> bool:
    if expr is None:
        return False
    if isinstance(expr, ast.Name):
        return expr.id in imported_names
    if isinstance(expr, ast.Attribute):
        root_name = _attribute_root_name(expr)
        return root_name in imported_names if root_name is not None else False
    return False


def _count_alias_bindings(tree: ast.Module, imported_names: set[str]) -> int:
    count = 0
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            if _is_import_alias_expr(node.value, imported_names):
                count += 1
        elif isinstance(node, ast.AnnAssign):
            if not isinstance(node.target, ast.Name):
                continue
            if _is_import_alias_expr(node.value, imported_names):
                count += 1
    return count


def _strip_leading_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if not body:
        return body
    first = body[0]
    if not isinstance(first, ast.Expr):
        return body
    value = first.value
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return body[1:]
    return body


def _is_delegating_stmt(stmt: ast.stmt, imported_names: set[str]) -> bool:
    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call):
        return _is_import_alias_expr(stmt.value.func, imported_names)
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return _is_import_alias_expr(stmt.value.func, imported_names)
    return False


def _count_delegating_callables(tree: ast.Module, imported_names: set[str]) -> tuple[int, int]:
    total = 0
    delegating = 0

    def visit_callable(node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        nonlocal total, delegating
        total += 1
        body = _strip_leading_docstring(list(node.body))
        if len(body) != 1:
            return
        if _is_delegating_stmt(body[0], imported_names):
            delegating += 1

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visit_callable(node)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    visit_callable(item)

    return total, delegating


def scan_delegation_candidate(path: Path) -> dict[str, Any] | None:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return None

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    import_nodes = _leading_import_nodes(tree)
    if not import_nodes:
        return None

    first_import = import_nodes[0]
    last_import = import_nodes[-1]
    import_lines = (last_import.end_lineno or last_import.lineno) - first_import.lineno + 1
    if import_lines < DELEGATION_IMPORT_BLOCK_MIN_LINES:
        return None

    imported_names = _imported_bindings(import_nodes)
    alias_bindings = _count_alias_bindings(tree, imported_names)
    callable_count, delegating_callables = _count_delegating_callables(tree, imported_names)
    score = alias_bindings + delegating_callables

    if score < DELEGATION_SCORE_MIN:
        return None
    if alias_bindings < DELEGATION_ALIAS_BINDINGS_MIN and delegating_callables < DELEGATION_DELEGATING_CALLABLES_MIN:
        return None

    return {
        "path": str(path),
        "import_lines": import_lines,
        "import_statements": len(import_nodes),
        "alias_bindings": alias_bindings,
        "delegating_callables": delegating_callables,
        "callables": callable_count,
        "score": score,
    }


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
    _allowlist: dict[str, str] = allowlist if allowlist is not None else load_flat_directory_allowlist(root)
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
            if rel_path in _allowlist:
                entry["allowed_reason"] = _allowlist[rel_path]
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
