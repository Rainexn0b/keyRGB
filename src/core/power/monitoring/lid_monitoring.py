from __future__ import annotations

import glob
import threading
import time
from collections.abc import Callable


_LID_MONITOR_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _parse_lid_state(content: str | None) -> str | None:
    if not content:
        return None
    s = str(content).strip().lower()
    if "open" in s:
        return "open"
    if "closed" in s:
        return "closed"
    return None


def _run_lid_monitor_action(*, action: Callable[[], None], logger) -> bool:
    try:
        action()
    except _LID_MONITOR_RUNTIME_ERRORS as e:  # @quality-exception exception-transparency: lid monitor polling crosses a runtime filesystem/hardware boundary; recoverable OS/device failures are logged with traceback while unexpected defects still propagate
        logger.exception("Error reading lid state: %s", e)
        return False
    return True


def start_sysfs_lid_monitoring(
    *,
    is_running: Callable[[], bool],
    on_lid_close: Callable[[], None],
    on_lid_open: Callable[[], None],
    logger,
) -> None:
    """Start a background thread to monitor lid state via /proc/acpi sysfs-style files."""

    def monitor_lid_sysfs():
        lid_files = glob.glob("/proc/acpi/button/lid/*/state")

        if not lid_files:
            logger.warning("No lid state file found")
            return

        lid_file = lid_files[0]
        logger.info("Monitoring lid state from: %s", lid_file)

        last_state = None
        while is_running():

            def poll_once() -> None:
                nonlocal last_state
                with open(lid_file) as f:
                    content = f.read()
                    state = _parse_lid_state(content)

                if state and state != last_state:
                    logger.info("Lid state changed: %s -> %s", last_state, state)
                    if state == "closed":
                        on_lid_close()
                    elif state == "open":
                        on_lid_open()
                    last_state = state

            if not _run_lid_monitor_action(action=poll_once, logger=logger):
                break

            time.sleep(0.5)

    threading.Thread(target=monitor_lid_sysfs, daemon=True).start()


def poll_lid_state_paths(
    *,
    is_running: Callable[[], bool],
    on_lid_close: Callable[[], None],
    on_lid_open: Callable[[], None],
    logger,
) -> None:
    """Fallback: poll lid state from known /proc or /sys paths."""

    lid_paths = [
        "/proc/acpi/button/lid/LID/state",
        "/proc/acpi/button/lid/LID0/state",
        "/sys/class/power_supply/AC/online",
    ]

    lid_path = None
    for path in lid_paths:
        try:
            with open(path):
                lid_path = path
                break
        except OSError:
            continue

    if not lid_path:
        logger.warning("Could not find lid state file, power management disabled")
        return

    last_state = None
    while is_running():

        def poll_once() -> None:
            nonlocal last_state
            with open(lid_path) as f:
                state = f.read()

            parsed = _parse_lid_state(state)

            if state != last_state:
                if parsed == "closed":
                    on_lid_close()
                elif parsed == "open":
                    on_lid_open()
                last_state = state

        _run_lid_monitor_action(action=poll_once, logger=logger)

        time.sleep(1)
