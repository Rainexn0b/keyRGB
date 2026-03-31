from __future__ import annotations

import glob
import threading
import time
from collections.abc import Callable


def _parse_lid_state(content: str | None) -> str | None:
    if not content:
        return None
    s = str(content).strip().lower()
    if "open" in s:
        return "open"
    if "closed" in s:
        return "closed"
    return None


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
            try:
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

            except Exception as e:
                logger.exception("Error reading lid state: %s", e)
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
            with open(path) as f:
                lid_path = path
                break
        except Exception:
            continue

    if not lid_path:
        logger.warning("Could not find lid state file, power management disabled")
        return

    last_state = None
    while is_running():
        try:
            with open(lid_path) as f:
                state = f.read()

            parsed = _parse_lid_state(state)

            if state != last_state:
                if parsed == "closed":
                    on_lid_close()
                elif parsed == "open":
                    on_lid_open()
                last_state = state

        except Exception as e:
            logger.exception("Error reading lid state: %s", e)

        time.sleep(1)
