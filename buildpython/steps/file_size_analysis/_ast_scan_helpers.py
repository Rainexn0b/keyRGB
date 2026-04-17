from __future__ import annotations

from dataclasses import dataclass

import ast
from pathlib import Path

from .constants import (
    DELEGATION_ALIAS_BINDINGS_MIN,
    DELEGATION_DELEGATING_CALLABLES_MIN,
    DELEGATION_IMPORT_BLOCK_MIN_LINES,
    DELEGATION_SCORE_MIN,
    REFACTOR_LINES,
)

ImportNode = ast.Import | ast.ImportFrom

_PURE_EXPORT_INIT_MAX_IMPORT_STATEMENTS = 3
_THIN_DELEGATION_LINES_PER_SCORE_POINT = 6


@dataclass(frozen=True)
class ModuleScanContext:
    path: Path
    source: str
    tree: ast.Module
    import_nodes: tuple[ImportNode, ...]
    imported_names: frozenset[str]


def module_docstring_consumes_first_statement(tree: ast.Module) -> bool:
    if not tree.body:
        return False
    first = tree.body[0]
    if not isinstance(first, ast.Expr):
        return False
    value = first.value
    return isinstance(value, ast.Constant) and isinstance(value.value, str)


def load_module_scan_context(path: Path) -> ModuleScanContext | None:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return None

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    import_nodes = tuple(_leading_import_nodes(tree))
    return ModuleScanContext(
        path=path,
        source=source,
        tree=tree,
        import_nodes=import_nodes,
        imported_names=frozenset(_imported_bindings(import_nodes)),
    )


def import_block_metrics(context: ModuleScanContext) -> tuple[int, int] | None:
    if not context.import_nodes:
        return None
    if _is_small_pure_export_init_facade(context):
        return None

    first = context.import_nodes[0]
    last = context.import_nodes[-1]
    return ((last.end_lineno or last.lineno) - first.lineno + 1, len(context.import_nodes))


def delegation_candidate_metrics(context: ModuleScanContext) -> dict[str, int | str] | None:
    import_block = import_block_metrics(context)
    if import_block is None:
        return None

    import_lines, import_statements = import_block
    if import_lines < DELEGATION_IMPORT_BLOCK_MIN_LINES:
        return None

    line_count = len(context.source.splitlines())
    alias_bindings = _count_alias_bindings(context.tree, context.imported_names)
    callable_count, delegating_callables = _count_delegating_callables(context.tree, context.imported_names)
    score = alias_bindings + delegating_callables

    if score < DELEGATION_SCORE_MIN:
        return None
    if alias_bindings < DELEGATION_ALIAS_BINDINGS_MIN and delegating_callables < DELEGATION_DELEGATING_CALLABLES_MIN:
        return None
    if _is_small_thin_delegation_facade(
        line_count=line_count,
        score=score,
        alias_bindings=alias_bindings,
        delegating_callables=delegating_callables,
        callable_count=callable_count,
    ):
        return None

    return {
        "path": str(context.path),
        "import_lines": import_lines,
        "import_statements": import_statements,
        "alias_bindings": alias_bindings,
        "delegating_callables": delegating_callables,
        "callables": callable_count,
        "score": score,
    }


def _leading_import_nodes(tree: ast.Module) -> list[ImportNode]:
    start_index = 1 if module_docstring_consumes_first_statement(tree) else 0
    import_nodes: list[ImportNode] = []
    for node in tree.body[start_index:]:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_nodes.append(node)
            continue
        break
    return import_nodes


def _imported_bindings(import_nodes: tuple[ImportNode, ...]) -> set[str]:
    bindings: set[str] = set()
    for node in import_nodes:
        for alias in node.names:
            bound = alias.asname or alias.name.split(".", 1)[0]
            if bound:
                bindings.add(bound)
    return bindings


def _explicit_reexport_bindings(import_nodes: tuple[ImportNode, ...]) -> set[str]:
    bindings: set[str] = set()
    for node in import_nodes:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        for alias in node.names:
            bound = alias.asname or alias.name.split(".", 1)[0]
            if bound:
                bindings.add(bound)
    return bindings


def _literal_export_names(expr: ast.expr | None) -> set[str] | None:
    if not isinstance(expr, (ast.List, ast.Tuple)):
        return None

    export_names: set[str] = set()
    for item in expr.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            return None
        export_names.add(item.value)
    return export_names or None


def _all_assignment_export_names(stmt: ast.stmt) -> set[str] | None:
    if isinstance(stmt, ast.Assign):
        if len(stmt.targets) != 1:
            return None
        target = stmt.targets[0]
        if not isinstance(target, ast.Name) or target.id != "__all__":
            return None
        return _literal_export_names(stmt.value)

    if isinstance(stmt, ast.AnnAssign):
        target = stmt.target
        if not isinstance(target, ast.Name) or target.id != "__all__":
            return None
        return _literal_export_names(stmt.value)

    return None


def _is_small_pure_export_init_facade(context: ModuleScanContext) -> bool:
    if context.path.name != "__init__.py":
        return False
    if len(context.import_nodes) > _PURE_EXPORT_INIT_MAX_IMPORT_STATEMENTS:
        return False

    start_index = 1 if module_docstring_consumes_first_statement(context.tree) else 0
    remaining_body = context.tree.body[start_index + len(context.import_nodes) :]
    if len(remaining_body) != 1:
        return False

    export_names = _all_assignment_export_names(remaining_body[0])
    if export_names is None:
        return False

    imported_names = _explicit_reexport_bindings(context.import_nodes)
    return bool(imported_names) and export_names == imported_names


def _attribute_root_name(expr: ast.expr) -> str | None:
    current = expr
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None


def _is_import_alias_expr(expr: ast.expr | None, imported_names: frozenset[str]) -> bool:
    if expr is None:
        return False
    if isinstance(expr, ast.Name):
        return expr.id in imported_names
    if isinstance(expr, ast.Attribute):
        root_name = _attribute_root_name(expr)
        return root_name in imported_names if root_name is not None else False
    return False


def _count_alias_bindings(tree: ast.Module, imported_names: frozenset[str]) -> int:
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


def _is_delegating_stmt(stmt: ast.stmt, imported_names: frozenset[str]) -> bool:
    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call):
        return _is_import_alias_expr(stmt.value.func, imported_names)
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return _is_import_alias_expr(stmt.value.func, imported_names)
    return False


def _count_delegating_callables(tree: ast.Module, imported_names: frozenset[str]) -> tuple[int, int]:
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


def _is_small_thin_delegation_facade(
    *,
    line_count: int,
    score: int,
    alias_bindings: int,
    delegating_callables: int,
    callable_count: int,
) -> bool:
    if line_count >= REFACTOR_LINES:
        return False
    if score * _THIN_DELEGATION_LINES_PER_SCORE_POINT >= line_count:
        return False
    if alias_bindings >= DELEGATION_ALIAS_BINDINGS_MIN:
        return True
    return callable_count > 0 and delegating_callables * 4 >= callable_count * 3
