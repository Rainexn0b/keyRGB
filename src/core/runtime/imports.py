from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Optional


def repo_root_from(anchor: str | Path) -> Path:
    """Best-effort repo root detection for running from a source checkout.

    Walks parent directories looking for a typical Python project layout.
    This also supports packaged layouts that keep the importable ``src/`` tree
    but do not ship ``pyproject.toml`` alongside the runtime files.
    """

    anchor_path = Path(anchor).resolve()
    candidates = [anchor_path] + list(anchor_path.parents)

    for parent in candidates:
        try:
            if (parent / "pyproject.toml").exists() and (parent / "src").exists():
                return parent
        except OSError:
            continue

    for parent in candidates:
        try:
            if (parent / "src").is_dir():
                return parent
        except OSError:
            continue

    # Fallback: assume we're somewhere under `<root>/src/...`.
    # Prefer the parent of the `src/` package when we can see it directly.
    try:
        src_index = next(index for index, parent in enumerate(anchor_path.parents) if parent.name == "src")
        return anchor_path.parents[src_index + 1]
    except (StopIteration, IndexError):
        pass

    try:
        return anchor_path.parents[2]
    except IndexError:
        return anchor_path.parent


def repo_root_str_from(anchor: str | Path) -> str:
    """Return :func:`repo_root_from` as a string path."""

    return str(repo_root_from(anchor))


def repo_root_cwd_from(anchor: str | Path, *, require_exists: bool = False) -> str | None:
    """Return a launcher ``cwd`` rooted at :func:`repo_root_from`.

    When ``require_exists`` is true, return ``None`` if the derived root does
    not currently exist on disk.
    """

    root = repo_root_from(anchor)
    if require_exists and not root.exists():
        return None
    return str(root)


def launcher_cwd_from(anchor: str | Path) -> str:
    """Return launcher cwd rooted at :func:`repo_root_from`.

    Launcher modules expect this path to exist because subprocess targets are
    imported from the checked-out or packaged ``src`` tree.
    """

    launcher_cwd = repo_root_cwd_from(anchor, require_exists=True)
    assert launcher_cwd is not None
    return launcher_cwd


def ensure_on_sys_path(path: Path) -> bool:
    """Ensure *path* is present on sys.path (at front)."""

    path_str = str(path)
    if path_str in sys.path:
        return False
    sys.path.insert(0, path_str)
    return True


def ensure_repo_root_on_sys_path(anchor: str | Path) -> Path:
    """Ensure the repo root is on sys.path and return it."""

    root = repo_root_from(anchor)
    ensure_on_sys_path(root)
    return root


def ensure_repo_root_on_sys_path_str(anchor: str | Path) -> str:
    """Ensure the repo root is on ``sys.path`` and return it as ``str``."""

    return str(ensure_repo_root_on_sys_path(anchor))


def add_first_existing_to_sys_path(paths: Iterable[Path]) -> Optional[Path]:
    """Insert the first existing path from *paths* to sys.path and return it."""

    for path in paths:
        try:
            if path.exists():
                ensure_on_sys_path(path)
                return path
        except OSError:
            continue
    return None
