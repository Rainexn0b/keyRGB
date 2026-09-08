from __future__ import annotations

import ast
from dataclasses import dataclass
from fnmatch import fnmatchcase
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
class _ScannedAssignment:
    target: str
    line: int


@dataclass(frozen=True)
class _ScannedCall:
    receiver: str
    method: str
    line: int
    lexical_locks: tuple[str, ...]
    literal_keywords: tuple[tuple[str, object], ...]


@dataclass(frozen=True)
class _ScannedLockAcquisition:
    lock: str
    line: int
    outer_locks: tuple[str, ...]


def _iter_rule_files(*, root: Path, rule: _ArchitectureRuleCorpus) -> list[Path]:
    matched: dict[str, Path] = {}
    for pattern in rule.include_globs:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            rel = _rel_path(root, path)
            if any(_path_matches_glob(rel, exclude) for exclude in rule.exclude_globs):
                continue
            matched[rel] = path
    return [matched[key] for key in sorted(matched)]


def _path_matches_glob(path: str, pattern: str) -> bool:
    """Match a repo-relative glob; ** covers zero or more whole directories."""

    def match(parts: tuple[str, ...], glob: tuple[str, ...]) -> bool:
        if not glob:
            return not parts
        if glob[0] == "**":
            return match(parts, glob[1:]) or bool(parts and match(parts[1:], glob))
        return bool(parts and fnmatchcase(parts[0], glob[0]) and match(parts[1:], glob[1:]))

    return match(PurePosixPath(path).parts, PurePosixPath(pattern).parts)


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


def _import_from_module(node: ast.ImportFrom, relative_path: str) -> str:
    """Resolve relative imports from the scanned file, without importing code."""

    if not node.level:
        return node.module or ""
    package = Path(relative_path).parent.parts
    if not relative_path or node.level > len(package):
        raise ValueError(f"Cannot resolve relative import in {relative_path!r}:{node.lineno}")
    prefix = package[: len(package) - node.level + 1]
    return ".".join((*prefix, *((node.module,) if node.module else ())))


def _scan_python_signals(
    text: str, *, relative_path: str = ""
) -> tuple[tuple[_ScannedImport, ...], tuple[_ScannedAttribute, ...]]:
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
            module = _import_from_module(node, relative_path)
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


def _scan_python_assignments(text: str) -> tuple[_ScannedAssignment, ...]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ()

    scanned_assignments: list[_ScannedAssignment] = []
    seen_assignments: set[tuple[str, int]] = set()

    def _record_target(target: ast.AST, fallback_line: int) -> None:
        if isinstance(target, (ast.List, ast.Tuple)):
            for element in target.elts:
                _record_target(element, fallback_line)
            return
        if isinstance(target, ast.Starred):
            _record_target(target.value, fallback_line)
            return

        dotted_target = _dotted_name(target)
        if dotted_target is None:
            return
        line = int(getattr(target, "lineno", fallback_line))
        key = (dotted_target, line)
        if key in seen_assignments:
            return
        seen_assignments.add(key)
        scanned_assignments.append(_ScannedAssignment(target=dotted_target, line=line))

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                _record_target(target, int(getattr(node, "lineno", 0)))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            _record_target(node.target, int(getattr(node, "lineno", 0)))

    scanned_assignments.sort(key=lambda item: (item.line, item.target))
    return tuple(scanned_assignments)


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


def _scan_python_lock_acquisitions(text: str) -> tuple[_ScannedLockAcquisition, ...]:
    """Collect lexical context-manager acquisitions without following calls.

    Function and lambda bodies start with an empty lock stack.  Class bodies
    retain the surrounding stack because class bodies execute immediately,
    matching the scope behavior of the call scanner above.  This intentionally
    provides no interprocedural proof for locks acquired in another function.
    """

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ()

    acquisitions: list[_ScannedLockAcquisition] = []

    class _LockVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._lexical_locks: list[str] = []

        def visit_With(self, node: ast.With) -> None:
            self._visit_with(node)

        def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
            self._visit_with(node)

        def _visit_with(self, node: ast.With | ast.AsyncWith) -> None:
            acquired = 0
            for item in node.items:
                self.visit(item.context_expr)
                context_name = _dotted_name(item.context_expr)
                if context_name is not None:
                    acquisitions.append(
                        _ScannedLockAcquisition(
                            lock=context_name,
                            line=int(getattr(item.context_expr, "lineno", getattr(node, "lineno", 0))),
                            outer_locks=tuple(self._lexical_locks),
                        )
                    )
                    self._lexical_locks.append(context_name)
                    acquired += 1
                if item.optional_vars is not None:
                    self.visit(item.optional_vars)
            for statement in node.body:
                self.visit(statement)
            if acquired:
                del self._lexical_locks[-acquired:]

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.generic_visit(node)

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

    _LockVisitor().visit(tree)
    acquisitions.sort(key=lambda item: (item.line, item.lock, item.outer_locks))
    return tuple(acquisitions)
