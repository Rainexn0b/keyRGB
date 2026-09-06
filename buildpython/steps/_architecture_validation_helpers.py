from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol


class _ArchitectureRuleCorpus(Protocol):
    @property
    def include_globs(self) -> tuple[str, ...]: ...

    @property
    def exclude_globs(self) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class _ScannedImport:
    module: str
    line: int


@dataclass(frozen=True)
class _ScannedAttribute:
    name: str
    line: int


@dataclass(frozen=True)
class _ScannedCall:
    receiver: str
    method: str
    line: int
    lexical_locks: tuple[str, ...]
    literal_keywords: tuple[tuple[str, object], ...]


def _iter_rule_files(*, root: Path, rule: _ArchitectureRuleCorpus) -> list[Path]:
    matched: dict[str, Path] = {}
    for pattern in rule.include_globs:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            rel = _rel_path(root, path)
            if any(PurePosixPath(rel).match(exclude) for exclude in rule.exclude_globs):
                continue
            matched[rel] = path
    return [matched[key] for key in sorted(matched)]


def _rel_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _line_number(*, text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _line_snippet(*, lines: list[str], line: int) -> str:
    if line <= 0 or line > len(lines):
        return ""
    return lines[line - 1].strip()[:200]


def _module_matches_import_rule(imported_module: str, forbidden_module: str) -> bool:
    return imported_module == forbidden_module or imported_module.startswith(f"{forbidden_module}.")


def _scan_python_signals(text: str) -> tuple[tuple[_ScannedImport, ...], tuple[_ScannedAttribute, ...]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return (), ()

    scanned_imports: list[_ScannedImport] = []
    seen_imports: set[tuple[str, int]] = set()
    scanned_attributes: list[_ScannedAttribute] = []
    seen_attributes: set[tuple[str, int]] = set()

    def _record_import(module: str, line: int) -> None:
        normalized = str(module).strip()
        if not normalized:
            return
        key = (normalized, int(line))
        if key in seen_imports:
            return
        seen_imports.add(key)
        scanned_imports.append(_ScannedImport(module=normalized, line=int(line)))

    def _record_attribute(name: str, line: int) -> None:
        normalized = str(name).strip()
        if not normalized:
            return
        key = (normalized, int(line))
        if key in seen_attributes:
            return
        seen_attributes.add(key)
        scanned_attributes.append(_ScannedAttribute(name=normalized, line=int(line)))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _record_import(alias.name, getattr(node, "lineno", 0))
            continue

        if isinstance(node, ast.ImportFrom):
            if int(getattr(node, "level", 0)) != 0:
                continue
            module = str(getattr(node, "module", "") or "").strip()
            if not module:
                continue
            line = int(getattr(node, "lineno", 0))
            _record_import(module, line)
            for alias in node.names:
                name = str(getattr(alias, "name", "") or "").strip()
                if not name or name == "*":
                    continue
                _record_import(f"{module}.{name}", line)
            continue

        if isinstance(node, ast.Attribute):
            _record_attribute(node.attr, int(getattr(node, "lineno", 0)))

    scanned_imports.sort(key=lambda item: (item.line, item.module))
    scanned_attributes.sort(key=lambda item: (item.line, item.name))
    return tuple(scanned_imports), tuple(scanned_attributes)


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        if parent is None:
            return None
        return f"{parent}.{node.attr}"
    return None


_NON_LITERAL = object()


def _literal_value(node: ast.AST) -> object:
    """Return a safe scalar AST literal, without evaluating arbitrary code."""

    if not isinstance(node, ast.Constant):
        return _NON_LITERAL
    value = node.value
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return _NON_LITERAL


def _scan_python_calls(text: str) -> tuple[_ScannedCall, ...]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ()

    scanned_calls: list[_ScannedCall] = []

    class _CallVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._lexical_locks: list[str] = []

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute):
                receiver = _dotted_name(node.func.value)
                if receiver is not None:
                    scanned_calls.append(
                        _ScannedCall(
                            receiver=receiver,
                            method=node.func.attr,
                            line=int(getattr(node, "lineno", 0)),
                            lexical_locks=tuple(self._lexical_locks),
                            literal_keywords=tuple(
                                (keyword.arg, value)
                                for keyword in node.keywords
                                if keyword.arg is not None
                                and (value := _literal_value(keyword.value)) is not _NON_LITERAL
                            ),
                        )
                    )
            self.generic_visit(node)

        def visit_With(self, node: ast.With) -> None:
            self._visit_with(node)

        def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
            self._visit_with(node)

        def _visit_with(self, node: ast.With | ast.AsyncWith) -> None:
            lock_count = 0
            for item in node.items:
                self.visit(item.context_expr)
                context_name = _dotted_name(item.context_expr)
                if context_name is not None:
                    self._lexical_locks.append(context_name)
                    lock_count += 1
                if item.optional_vars is not None:
                    self.visit(item.optional_vars)
            for statement in node.body:
                self.visit(statement)
            if lock_count:
                del self._lexical_locks[-lock_count:]

        def _visit_nested_scope(self, node: ast.AST) -> None:
            saved_locks = self._lexical_locks
            self._lexical_locks = []
            self.generic_visit(node)
            self._lexical_locks = saved_locks

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_function_definition(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_function_definition(node)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            for default in (*node.args.defaults, *node.args.kw_defaults):
                if default is not None:
                    self.visit(default)
            saved_locks = self._lexical_locks
            self._lexical_locks = []
            self.visit(node.body)
            self._lexical_locks = saved_locks

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.generic_visit(node)

        def _visit_function_definition(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            for decorator in node.decorator_list:
                self.visit(decorator)
            for default in (*node.args.defaults, *node.args.kw_defaults):
                if default is not None:
                    self.visit(default)
            saved_locks = self._lexical_locks
            self._lexical_locks = []
            for statement in node.body:
                self.visit(statement)
            self._lexical_locks = saved_locks

    _CallVisitor().visit(tree)
    scanned_calls.sort(key=lambda item: (item.line, item.receiver, item.method))
    return tuple(scanned_calls)
