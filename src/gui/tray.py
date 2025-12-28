#!/usr/bin/env python3
"""KeyRGB tray entrypoint.

This module is the stable entrypoint used by the `keyrgb` launcher:
`python3 -m src.gui.tray`.

The tray implementation lives in `src.tray`.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_repo_root_on_syspath() -> None:
    try:
        repo_root = Path(__file__).resolve().parents[2]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
    except Exception:
        pass


_ensure_repo_root_on_syspath()

from src.tray import KeyRGBTray, main  # noqa: E402


__all__ = ["KeyRGBTray", "main"]


if __name__ == "__main__":
    main()
