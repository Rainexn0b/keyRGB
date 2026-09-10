"""Exception-transparency guard for new/edited calibrator modules.

Mirrors build step 19 (exception transparency): no bare ``except:``, no
``except Exception`` / ``except BaseException`` in the guided-session,
preview-journal, launch, app, logic, bootstrap, or preview surface.  Narrow
tuples keep failures diagnosable; ``GuidedSessionError`` chains its cause.
"""

from __future__ import annotations

import ast
from pathlib import Path

MODULES = [
    "keyrgb/gui/calibrator/guided/__init__.py",
    "keyrgb/gui/calibrator/guided/session_protocol.py",
    "keyrgb/gui/calibrator/guided/session_storage.py",
    "keyrgb/gui/calibrator/guided/config_view.py",
    "keyrgb/gui/calibrator/guided/journal_model.py",
    "keyrgb/gui/calibrator/guided/journal_store.py",
    "keyrgb/gui/calibrator/guided/journal_recovery.py",
    "keyrgb/gui/calibrator/launch.py",
    "keyrgb/gui/calibrator/app.py",
    "keyrgb/gui/calibrator/_app_logic.py",
    "keyrgb/gui/calibrator/_app_bootstrap.py",
    "keyrgb/gui/calibrator/helpers/keyboard_preview.py",
]

_BROAD_NAMES = {"Exception", "BaseException"}


def _broad_handlers(tree: ast.AST) -> list[str]:
    aliases: dict[str, ast.expr] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    aliases[target.id] = node.value

    def _names(expr: ast.expr | None, seen: frozenset[str] = frozenset()) -> set[str]:
        if expr is None:
            return set()
        if isinstance(expr, ast.Name):
            if expr.id in aliases and expr.id not in seen:
                return _names(aliases[expr.id], seen | {expr.id})
            return {expr.id}
        if isinstance(expr, ast.Attribute):
            return {expr.attr}
        if isinstance(expr, ast.Tuple):
            out: set[str] = set()
            for elt in expr.elts:
                out |= _names(elt, seen)
            return out
        return set()

    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                problems.append(f"bare except at line {node.lineno}")
            elif _names(node.type) & _BROAD_NAMES:
                problems.append(f"broad except at line {node.lineno}")
    return problems


def test_no_broad_exception_handlers_in_guided_surface() -> None:
    root = Path(__file__).resolve().parents[4]
    failures: list[str] = []
    for rel in MODULES:
        tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        for problem in _broad_handlers(tree):
            failures.append(f"{rel}: {problem}")
    assert failures == []


def test_guided_errors_chain_transparently() -> None:
    """GuidedSessionError re-raises must use ``raise ... from`` where a cause exists."""

    root = Path(__file__).resolve().parents[4]
    tree = ast.parse((root / "keyrgb/gui/calibrator/guided/session_storage.py").read_text(encoding="utf-8"))

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.unhandled: list[int] = []
            self._handler_depth = 0

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            self._handler_depth += 1
            self.generic_visit(node)
            self._handler_depth -= 1

        def visit_Raise(self, node: ast.Raise) -> None:
            if self._handler_depth > 0 and node.exc is not None and node.cause is None:
                self.unhandled.append(node.lineno)
            self.generic_visit(node)

    visitor = _Visitor()
    visitor.visit(tree)
    assert visitor.unhandled == []
