from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


_TOP_LEVEL_ROOT_FILES = ("keyrgb", "keyrgb-tuxedo")
_EXTERNAL_ROOT_DIRS = ("scripts",)


@dataclass(frozen=True)
class UsageGraph:
    reverse_adjacency: dict[Path, set[Path]]
    reachable: frozenset[Path]
    external_inbound_counts: dict[Path, int]
    root_paths: frozenset[Path]


def build_usage_graph(root: Path, *, roots: tuple[str, ...]) -> UsageGraph:
    files = _iter_internal_python_files(root, roots=roots)
    module_index = _module_index(root, files)
    external_root_files = _iter_external_root_files(root)

    adjacency: dict[Path, set[Path]] = {}
    reverse_adjacency: dict[Path, set[Path]] = {}
    for path in files:
        dependencies = _scan_internal_dependencies(root, path, module_index)
        adjacency[path] = dependencies
        for dependency in dependencies:
            reverse_adjacency.setdefault(dependency, set()).add(path)

    external_inbound_counts: dict[Path, int] = {}
    root_paths = _collect_root_paths(root, module_index, external_inbound_counts, external_root_files=external_root_files)
    reachable = _reachable_paths(adjacency, root_paths) if root_paths else frozenset()

    launched_module_roots = _collect_launched_module_roots(
        module_index,
        files=[*external_root_files, *sorted(reachable)],
    )
    if launched_module_roots.difference(root_paths):
        root_paths = frozenset(sorted(set(root_paths) | launched_module_roots))
        reachable = _reachable_paths(adjacency, root_paths)

    return UsageGraph(
        reverse_adjacency=reverse_adjacency,
        reachable=reachable,
        external_inbound_counts=external_inbound_counts,
        root_paths=root_paths,
    )


def inbound_import_count(graph: UsageGraph, path: Path) -> int:
    return len(graph.reverse_adjacency.get(path, set())) + graph.external_inbound_counts.get(path, 0)


def _iter_internal_python_files(root: Path, *, roots: tuple[str, ...]) -> list[Path]:
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


def _module_index(root: Path, files: list[Path]) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in files:
        module_name = _module_name_for_path(root, path)
        if module_name is not None:
            index[module_name] = path
    return index


def _module_name_for_path(root: Path, path: Path) -> str | None:
    try:
        rel_path = path.relative_to(root)
    except ValueError:
        return None

    if rel_path.suffix != ".py":
        return None
    if not rel_path.parts or rel_path.parts[0] not in {"src", "buildpython"}:
        return None

    parts = list(rel_path.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts) if parts else None


def _scan_internal_dependencies(root: Path, path: Path, module_index: dict[str, Path]) -> set[Path]:
    module_name = _module_name_for_path(root, path)
    if module_name is None:
        return set()

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return set()

    dependencies: set[Path] = set()
    package_name = _package_name_for_module(module_name, path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                dependency = module_index.get(alias.name)
                if dependency is not None:
                    dependencies.add(dependency)
        elif isinstance(node, ast.ImportFrom):
            dependencies.update(_resolve_from_import(node, package_name=package_name, module_index=module_index))
    return dependencies


def _package_name_for_module(module_name: str, path: Path) -> str:
    if path.name == "__init__.py":
        return module_name
    if "." not in module_name:
        return ""
    return module_name.rsplit(".", 1)[0]


def _resolve_from_import(
    node: ast.ImportFrom,
    *,
    package_name: str,
    module_index: dict[str, Path],
) -> set[Path]:
    dependencies: set[Path] = set()
    base_module_name = _from_import_base_module_name(node, package_name=package_name)
    if base_module_name is None:
        return dependencies

    base_dependency = module_index.get(base_module_name)
    if base_dependency is not None:
        dependencies.add(base_dependency)

    for alias in node.names:
        if alias.name == "*":
            continue
        child_module_name = f"{base_module_name}.{alias.name}" if base_module_name else alias.name
        dependency = module_index.get(child_module_name)
        if dependency is not None:
            dependencies.add(dependency)

    return dependencies


def _from_import_base_module_name(node: ast.ImportFrom, *, package_name: str) -> str | None:
    if node.level:
        package_parts = package_name.split(".") if package_name else []
        ascend = node.level - 1
        if ascend > len(package_parts):
            return None
        if ascend:
            package_parts = package_parts[: len(package_parts) - ascend]
        base = ".".join(package_parts)
        if node.module:
            return f"{base}.{node.module}" if base else node.module
        return base or None

    return node.module


def _collect_root_paths(
    root: Path,
    module_index: dict[str, Path],
    external_inbound_counts: dict[Path, int],
    *,
    external_root_files: list[Path],
) -> frozenset[Path]:
    root_paths: set[Path] = set()

    for module_name in _entrypoint_modules_from_pyproject(root):
        path = module_index.get(module_name)
        if path is not None:
            root_paths.add(path)

    for module_name, path in module_index.items():
        if path.name == "__main__.py" and module_name.startswith(("src.", "buildpython.")):
            root_paths.add(path)

    for external_path in external_root_files:
        for dependency in _scan_external_dependencies(root, external_path, module_index):
            root_paths.add(dependency)
            external_inbound_counts[dependency] = external_inbound_counts.get(dependency, 0) + 1

    return frozenset(sorted(root_paths))


def _entrypoint_modules_from_pyproject(root: Path) -> set[str]:
    pyproject = root / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return set()

    modules: set[str] = set()
    in_scripts = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            in_scripts = stripped == "[project.scripts]"
            continue
        if not in_scripts or "=" not in stripped:
            continue

        value = stripped.split("=", 1)[1].strip()
        if not value.startswith('"'):
            continue
        closing_quote = value.find('"', 1)
        if closing_quote == -1:
            continue

        entrypoint = value[1:closing_quote]
        module_name = entrypoint.split(":", 1)[0].strip()
        if module_name.startswith(("src", "buildpython")):
            modules.add(module_name)

    return modules


def _iter_external_root_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for name in _TOP_LEVEL_ROOT_FILES:
        path = root / name
        if path.exists() and path.is_file():
            files.append(path)

    for folder_name in _EXTERNAL_ROOT_DIRS:
        folder = root / folder_name
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            files.append(path)

    return sorted(files)


def _scan_external_dependencies(root: Path, path: Path, module_index: dict[str, Path]) -> set[Path]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return set()

    dependencies: set[Path] = set()
    external_module_name = _module_name_for_path(root, path)
    package_name = _package_name_for_module(external_module_name, path) if external_module_name is not None else ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                dependency = module_index.get(alias.name)
                if dependency is not None:
                    dependencies.add(dependency)
        elif isinstance(node, ast.ImportFrom):
            dependencies.update(_resolve_from_import(node, package_name=package_name, module_index=module_index))
    return dependencies


def _collect_launched_module_roots(module_index: dict[str, Path], *, files: list[Path]) -> set[Path]:
    root_paths: set[Path] = set()
    for path in files:
        for module_name in _launched_module_names(path):
            dependency = module_index.get(module_name)
            if dependency is not None:
                root_paths.add(dependency)
    return root_paths


def _launched_module_names(path: Path) -> set[str]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return set()

    module_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for expr in node.args:
            tokens = _string_tokens(expr)
            if not tokens:
                continue
            for index, token in enumerate(tokens[:-1]):
                if token != "-m":
                    continue
                module_name = tokens[index + 1]
                if module_name.startswith(("src.", "buildpython.")):
                    module_names.add(module_name)
    return module_names


def _string_tokens(expr: ast.expr) -> list[str]:
    if isinstance(expr, (ast.List, ast.Tuple)):
        tokens: list[str] = []
        for item in expr.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                tokens.append(item.value)
        return tokens
    return []


def _reachable_paths(adjacency: dict[Path, set[Path]], root_paths: frozenset[Path]) -> frozenset[Path]:
    reachable: set[Path] = set()
    queue = list(root_paths)

    while queue:
        current = queue.pop()
        if current in reachable:
            continue
        reachable.add(current)
        for dependency in adjacency.get(current, set()):
            if dependency not in reachable:
                queue.append(dependency)

    return frozenset(reachable)