"""Tray startup entrypoint.

This module owns the startup sequence (logging, diagnostics, single-instance)
and then launches the `KeyRGBTray` application.
"""

from __future__ import annotations

import logging
import signal
import sys
from collections.abc import Sequence

from keyrgb.core.diagnostics.diagnostic_session import diagnostic_session_from_cli
from keyrgb.core.diagnostics.runtime_capture import capture_runtime_log_from_cli

from .app.application import KeyRGBTray
from .app.lifecycle import shutdown_tray_runtime_best_effort
from .startup import (
    acquire_single_instance_or_exit,
    configure_logging,
    log_startup_diagnostics_if_debug,
)

logger = logging.getLogger(__name__)

_TRAY_ENTRYPOINT_RUNTIME_ERRORS = (
    AttributeError,
    ImportError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _shutdown_engine_best_effort(app: object | None) -> None:
    """Stop runtime producers and release USB devices before process exit.

    Without this, the reactive render thread races with libusb teardown on
    Ctrl-C / SIGTERM, causing ``usbi_mutex_destroy`` / ``usbi_mutex_lock``
    C-level assertion failures (core dump) because the device handle is closed
    while an in-flight ``ctrl_transfer`` still holds the libusb mutex.

    ``engine.close()`` calls ``stop()`` first (joins the render thread with a
    2 s timeout), then atomically swaps the device to a ``NullKeyboard``
    under ``kb_lock`` before closing the real device — so the render thread
    can no longer touch USB after this returns.
    """

    if app is None:
        return
    shutdown_tray_runtime_best_effort(app)


def main(argv: Sequence[str] | None = None) -> None:
    argv_tuple = tuple(sys.argv[1:] if argv is None else argv)

    # Diagnostic session takes priority: it launches a full debug child in the
    # foreground and returns that child's exit status. Keep this before the
    # capture-log path so a single ``--diagnostic-session`` does not also trigger
    # the older capture-only flow.
    session_exit_code = diagnostic_session_from_cli(argv_tuple, prog="keyrgb")
    if session_exit_code is not None:
        if session_exit_code != 0:
            raise SystemExit(session_exit_code)
        return

    capture_exit_code = capture_runtime_log_from_cli(argv_tuple, prog="keyrgb")
    if capture_exit_code is not None:
        if capture_exit_code != 0:
            raise SystemExit(capture_exit_code)
        return

    app: KeyRGBTray | None = None
    try:
        configure_logging()
        log_startup_diagnostics_if_debug()
        acquire_single_instance_or_exit()

        # Ensure the engine is stopped and the USB device is released on
        # SIGTERM (desktop session logout / systemd stop) as well as Ctrl-C.
        def _signal_shutdown(signum: int, *_args: object) -> None:
            raise SystemExit(128 + signum)

        signal.signal(signal.SIGTERM, _signal_shutdown)

        app = KeyRGBTray()

        app.run()

    except KeyboardInterrupt:
        logger.info("Shutting down (Ctrl-C)...")
        sys.exit(0)
    except SystemExit:
        # SIGTERM handler raises SystemExit; let finally handle cleanup.
        raise
    except _TRAY_ENTRYPOINT_RUNTIME_ERRORS:  # @quality-exception exception-transparency: outermost process boundary; recoverable startup/runtime failures are logged with traceback before clean exit
        logger.exception("Unhandled error")
        sys.exit(1)
    finally:
        # Always close the engine, even when pystray swallows KeyboardInterrupt
        # internally and ``app.run()`` returns normally. Without this, the
        # reactive render thread keeps doing USB writes during interpreter
        # teardown, racing with libusb device-handle cleanup and triggering
        # ``usbi_mutex_destroy`` / ``usbi_mutex_lock`` C-level assertions.
        _shutdown_engine_best_effort(app)
