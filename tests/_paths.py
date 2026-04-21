from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from src.core.runtime.imports import ensure_repo_root_on_sys_path_str, repo_root_str_from
except ModuleNotFoundError:  # pragma: no cover - keeps bootstrap resilient to import order
    ensure_repo_root_on_sys_path_str = None
    repo_root_str_from = None


if repo_root_str_from is not None:
    REPO_ROOT = repo_root_str_from(__file__)
else:
    REPO_ROOT = os.fspath(Path(__file__).resolve().parents[1])


def ensure_repo_root_on_sys_path() -> str:
    if ensure_repo_root_on_sys_path_str is not None:
        return ensure_repo_root_on_sys_path_str(__file__)

    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)

    return REPO_ROOT
