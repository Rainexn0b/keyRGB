from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Iterable, Iterator
from typing import Optional

_logger = logging.getLogger(__name__)


def iter_prepare_for_sleep_events(lines: Iterable[str]) -> Iterator[bool]:
    """Parse `dbus-monitor` output for logind PrepareForSleep events.

    Yields:
        True for suspend (going to sleep), False for resume (waking up).

    This logic intentionally mirrors the legacy behavior in `PowerManager._monitor_loop`.
    """

    it = iter(lines)
    for line in it:
        if "PrepareForSleep" not in line:
            continue

        try:
            next_line = next(it)
        except StopIteration:
            return

        if "boolean true" in next_line:
            yield True
        elif "boolean false" in next_line:
            yield False


def monitor_prepare_for_sleep(
    *,
    is_running: Callable[[], bool],
    on_suspend: Callable[[], None],
    on_resume: Callable[[], None],
    on_started: Optional[Callable[[], None]] = None,
) -> None:
    """Run `dbus-monitor` for logind PrepareForSleep and invoke callbacks."""

    cmd = [
        "dbus-monitor",
        "--system",
        "type='signal',interface='org.freedesktop.login1.Manager',member='PrepareForSleep'",
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1,
    )

    # For type-checkers: stdout is only None if stdout=DEVNULL/None.
    assert process.stdout is not None

    try:
        if on_started is not None:
            on_started()

        # Read incrementally to preserve the original behavior.
        while is_running():
            line = process.stdout.readline()
            if not line:
                break

            if "PrepareForSleep" not in line:
                continue

            next_line = process.stdout.readline()
            if "boolean true" in next_line:
                on_suspend()
            elif "boolean false" in next_line:
                on_resume()
    finally:
        _terminate_process(process)


def _terminate_process(process: subprocess.Popen) -> None:
    """Best-effort termination and cleanup of a Popen subprocess."""
    terminate = getattr(process, "terminate", None)
    if callable(terminate):
        try:
            terminate()
        except OSError:
            _logger.debug("Could not terminate dbus-monitor process", exc_info=True)

    wait = getattr(process, "wait", None)
    if callable(wait):
        try:
            wait(timeout=2)
        except subprocess.TimeoutExpired:
            _logger.debug("dbus-monitor process did not exit within timeout after terminate; killing")
            kill = getattr(process, "kill", None)
            if callable(kill):
                try:
                    kill()
                except OSError:
                    _logger.debug("Could not kill dbus-monitor process", exc_info=True)
        except OSError:
            pass
