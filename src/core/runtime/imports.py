from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Optional
import os


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


def ensure_ite8291r3_ctl_importable(anchor: str | Path) -> Optional[Path]:
    """Try to make `ite8291r3_ctl` importable from a source checkout.

    Returns the inserted path if a repo/vendored fallback was used, else None.
    """

    # If explicitly requested, never override the installed module.
    if os.environ.get("KEYRGB_USE_INSTALLED_ITE") == "1":
        return None

    # Under pytest, callers often monkeypatch `sys.modules["ite8291r3_ctl"]`.
    # Do not stomp on that by force-prepending vendored paths.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            import ite8291r3_ctl  # noqa: F401
            return None
        except ImportError:
            root = repo_root_from(anchor)
            candidates = [
                root / "vendor" / "ite8291r3-ctl",
                root / "ite8291r3-ctl",  # legacy layout
            ]
            return add_first_existing_to_sys_path(candidates)

    existing = sys.modules.get("ite8291r3_ctl")
    if existing is not None and not getattr(existing, "__file__", None):
        # Likely an in-memory test double; leave it alone.
        return None

    root = repo_root_from(anchor)
    candidates = [
        root / "vendor" / "ite8291r3-ctl",
        root / "ite8291r3-ctl",  # legacy layout
    ]

    # Prefer a vendored checkout when it exists, even if a system-installed
    # `ite8291r3_ctl` is already importable. This keeps dev/source runs stable
    # when the distro package lags behind required USB IDs/patches.
    inserted = add_first_existing_to_sys_path(candidates)
    if inserted is None:
        return None

    # If the module was already imported from elsewhere (e.g. site-packages),
    # force a reload so the vendored path wins.
    already_loaded = any(name == "ite8291r3_ctl" or name.startswith("ite8291r3_ctl.") for name in sys.modules)
    if already_loaded:
        for name in list(sys.modules.keys()):
            if name == "ite8291r3_ctl" or name.startswith("ite8291r3_ctl."):
                sys.modules.pop(name, None)

    return inserted
