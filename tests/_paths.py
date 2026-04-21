from __future__ import annotations

import os
import sys
from pathlib import Path

def _runtime_path_helpers() -> tuple[object | None, object | None]:
    try:
        from src.core.runtime.imports import ensure_repo_root_on_sys_path_str, repo_root_str_from
    except ModuleNotFoundError:  # pragma: no cover - keeps bootstrap resilient to import order
        return None, None
    return ensure_repo_root_on_sys_path_str, repo_root_str_from


def _fallback_repo_root_str(anchor: str | Path) -> str:
    return os.fspath(Path(anchor).resolve().parents[1])


def _repo_root_str(anchor: str | Path) -> str:
    _ensure_fn, repo_root_fn = _runtime_path_helpers()
    if callable(repo_root_fn):
        return repo_root_fn(anchor)
    return _fallback_repo_root_str(anchor)


REPO_ROOT = _repo_root_str(__file__)


def ensure_repo_root_on_sys_path() -> str:
    ensure_fn, _repo_root_fn = _runtime_path_helpers()
    if callable(ensure_fn):
        return ensure_fn(__file__)

    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)

    return REPO_ROOT
