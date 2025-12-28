"""Tray application implementation.

This package holds the KeyRGB system tray app logic. Historically the project
had multiple tray entrypoints (e.g. `src/gui/tray.py`, `src/tray_app.py`).
Those modules now delegate into this package to avoid duplication.
"""

from .app import KeyRGBTray, main

__all__ = ["KeyRGBTray", "main"]
