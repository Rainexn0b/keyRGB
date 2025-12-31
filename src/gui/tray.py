#!/usr/bin/env python3
"""KeyRGB tray entrypoint.

This module is the stable entrypoint used by the `keyrgb` launcher:
`python3 -m src.gui.tray`.

The tray implementation lives in `src.tray`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.core.imports import ensure_repo_root_on_sys_path


def _ensure_repo_root_on_syspath() -> None:
    ensure_repo_root_on_sys_path(Path(__file__))


_ensure_repo_root_on_syspath()

from src.tray import KeyRGBTray, main  # noqa: E402


__all__ = ["KeyRGBTray", "main"]


if __name__ == "__main__":
    main()
