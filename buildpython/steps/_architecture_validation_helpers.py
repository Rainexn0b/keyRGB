from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Protocol


class _ArchitectureRuleCorpus(Protocol):
    @property
    def include_globs(self) -> tuple[str, ...]:
        ...

    @property
    def exclude_globs(self) -> tuple[str, ...]:
        ...


@dataclass(frozen=True)
class _ScannedImport:
    module: str
    line: int


@dataclass(frozen=True)
class _ScannedAttribute:
    name: str
    line: int


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