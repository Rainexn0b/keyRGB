from __future__ import annotations

from dataclasses import dataclass

import ast
from pathlib import Path

ImportNode = ast.Import | ast.ImportFrom


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


def _alias_binding_target_name(stmt: ast.stmt, imported_names: frozenset[str]) -> str | None:
    if isinstance(stmt, ast.Assign):
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            return None
        target_name = stmt.targets[0].id
        if target_name == "__all__":
            return None
        return target_name if _is_import_alias_expr(stmt.value, imported_names) else None

    if isinstance(stmt, ast.AnnAssign):
        if not isinstance(stmt.target, ast.Name) or stmt.target.id == "__all__":
            return None
        return stmt.target.id if _is_import_alias_expr(stmt.value, imported_names) else None

    return None