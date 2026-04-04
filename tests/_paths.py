from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = os.fspath(Path(__file__).resolve().parents[1])


def ensure_repo_root_on_sys_path() -> str:
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    return REPO_ROOT
