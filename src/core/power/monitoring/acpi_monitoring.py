from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from typing import Optional

from .lid_monitoring import poll_lid_state_paths

_logger = logging.getLogger(__name__)


def _parse_acpi_lid_event(line: str | None) -> str | None:
    if not line:
        return None
    s = str(line).strip().lower()
    if "button/lid" not in s:
        return None
    if "close" in s:
        return "closed"
    if "open" in s:
        return "open"
    return None


def _terminate_process(process: subprocess.Popen) -> None:
    """Best-effort termination and cleanup of a Popen subprocess."""
    terminate = getattr(process, "terminate", None)
    if callable(terminate):
        try:
            terminate()
        except OSError:
            _logger.debug("Could not terminate acpi_listen process", exc_info=True)

    wait = getattr(process, "wait", None)
    if callable(wait):
        try:
            wait(timeout=2)
        except subprocess.TimeoutExpired:
            _logger.debug("acpi_listen process did not exit within timeout after terminate; killing")
            kill = getattr(process, "kill", None)
            if callable(kill):
                try:
                    kill()
                except OSError:
                    _logger.debug("Could not kill acpi_listen process", exc_info=True)
        except OSError:
            pass


def monitor_acpi_events(
    *,
    is_running: Callable[[], bool],
    on_lid_close: Callable[[], None],
    on_lid_open: Callable[[], None],
    logger,
) -> None:
    """Fallback method using acpi_listen for lid events.

    If `acpi_listen` isn't available, falls back to polling lid state paths.
    """

    process: Optional[subprocess.Popen] = None

    try:
        process = subprocess.Popen(
            ["acpi_listen"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            bufsize=1,
        )

        assert process.stdout is not None

        while is_running():
            line = process.stdout.readline()
            if not line:
                break

            event = _parse_acpi_lid_event(line)
            if event == "closed":
                on_lid_close()
            elif event == "open":
                on_lid_open()

    except FileNotFoundError:
        poll_lid_state_paths(
            is_running=is_running,
            on_lid_close=on_lid_close,
            on_lid_open=on_lid_open,
            logger=logger,
        )
    finally:
        if process is not None:
            _terminate_process(process)
