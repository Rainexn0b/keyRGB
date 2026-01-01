"""Tray startup entrypoint.

This module owns the startup sequence (logging, diagnostics, single-instance)
and then launches the `KeyRGBTray` application.
"""

from __future__ import annotations

import logging
import sys

from .application import KeyRGBTray
from .startup import acquire_single_instance_or_exit, configure_logging, log_startup_diagnostics_if_debug

logger = logging.getLogger(__name__)


def main() -> None:
    try:
        configure_logging()
        log_startup_diagnostics_if_debug()
        acquire_single_instance_or_exit()

        app = KeyRGBTray()
        app.run()

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as exc:
        logger.exception("Unhandled error: %s", exc)
        sys.exit(1)
