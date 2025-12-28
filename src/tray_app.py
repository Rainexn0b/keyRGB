#!/usr/bin/env python3
"""Legacy tray entrypoint.

This file is kept for backwards compatibility with older launch scripts.
The maintained tray implementation lives in `src.tray`.

Prefer running: `python -m src.tray.app`
"""

from __future__ import annotations

from src.tray.app import main as tray_main


def main() -> None:
    tray_main()


if __name__ == "__main__":
    main()
