from __future__ import annotations

import ast

from ..constants import (
    DELEGATION_ALIAS_BINDINGS_MIN,
    DELEGATION_DELEGATING_CALLABLES_MIN,
    DELEGATION_IMPORT_BLOCK_MIN_LINES,
    DELEGATION_SCORE_MIN,
    REFACTOR_LINES,
)
from .context import ModuleScanContext, _is_import_alias_expr
from .import_blocks import import_block_metrics

_THIN_DELEGATION_LINES_PER_SCORE_POINT = 6


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