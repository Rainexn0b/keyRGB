#!/usr/bin/env python3
"""KeyRGB tray app entrypoint.

Kept as a stable importable entrypoint for:
- `python -m src.gui.tray` (packaged launcher)
- `python -m src.tray.app` (preferred)
- legacy `src/tray_app.py`

The tray class implementation lives in `src.tray.application`.
"""

from __future__ import annotations

import sys

import logging

from .application import KeyRGBTray
from .startup import acquire_single_instance_or_exit, configure_logging, log_startup_diagnostics_if_debug

logger = logging.getLogger(__name__)


def main():
    try:
        configure_logging()
        log_startup_diagnostics_if_debug()
        acquire_single_instance_or_exit()

        app = KeyRGBTray()
        app.run()

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
        sys.exit(1)


if __name__ == '__main__':
    main()
