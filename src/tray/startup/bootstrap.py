from __future__ import annotations

import logging
import os
import sys

from src.core.diagnostics import collect_diagnostics, format_diagnostics_text

from ..integrations import runtime


logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure root logging for the tray app.

    This is intentionally small and best-effort: if callers already configured
    logging handlers, we don't override them.
    """

    if logging.getLogger().handlers:
        return

    level = logging.DEBUG if os.environ.get("KEYRGB_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


def log_startup_diagnostics_if_debug() -> None:
    """Log diagnostics on startup when KEYRGB_DEBUG is enabled.

    Best-effort only; must never fail app startup.
    """

    if not os.environ.get("KEYRGB_DEBUG"):
        return

    try:
        diag = collect_diagnostics(include_usb=True)
        logger.debug("Startup diagnostics (Tongfang):\n%s", format_diagnostics_text(diag))
    except Exception:
        # Best-effort; never fail startup because of diagnostics.
        return


def acquire_single_instance_or_exit() -> None:
    """Acquire the tray single-instance lock or exit with code 0."""

    if runtime.acquire_single_instance_lock():
        return

    logger.error("KeyRGB is already running (lock held). Not starting a second instance.")
    sys.exit(0)
