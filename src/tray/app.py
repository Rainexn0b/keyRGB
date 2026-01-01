#!/usr/bin/env python3
"""KeyRGB tray app entrypoint.

Kept as a stable importable entrypoint for:
- `python -m src.gui.tray` (packaged launcher)
- `python -m src.tray.app` (preferred)
- legacy `src/tray_app.py`

The tray class implementation lives in `src.tray.application`.
"""

from __future__ import annotations

from .application import KeyRGBTray
from .entrypoint import main


if __name__ == '__main__':
    main()
