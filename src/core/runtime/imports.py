from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Optional


def repo_root_from(anchor: str | Path) -> Path:
    """Best-effort repo root detection for running from a source checkout.

    Walks parent directories looking for a typical Python project layout.
    """

    anchor_path = Path(anchor).resolve()
    candidates = [anchor_path] + list(anchor_path.parents)

    for parent in candidates:
        try:
            if (parent / "pyproject.toml").exists() and (parent / "src").exists():
                return parent
        except OSError:
            continue

    # Fallback: assume we're somewhere under `<root>/src/...`.
    # `parents[2]` is usually `<root>` for `<root>/src/<pkg>/file.py`.
    try:
        return anchor_path.parents[2]
    except IndexError:
        return anchor_path.parent


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
