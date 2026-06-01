from __future__ import annotations

import glob
import os
import threading
import time
from collections.abc import Callable


_LID_MONITOR_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_PROC_LID_STATE_GLOB = "/proc/acpi/button/lid/*/state"
_FALLBACK_LID_STATE_PATHS = (
    "/proc/acpi/button/lid/LID/state",
    "/proc/acpi/button/lid/LID0/state",
    "/proc/acpi/button/lid/LID1/state",
)


def _brightness_debug_enabled() -> bool:
    value = os.environ.get("KEYRGB_DEBUG_BRIGHTNESS", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_lid_state(content: str | None) -> str | None:
    if not content:
        return None
    s = str(content).strip().lower()
    if "open" in s:
        return "open"
    if "closed" in s:
        return "closed"
    return None


def _lid_state_paths() -> list[str]:
    paths: list[str] = []
    for path in glob.glob(_PROC_LID_STATE_GLOB):
        if path not in paths:
            paths.append(path)
    for path in _FALLBACK_LID_STATE_PATHS:
        if path not in paths:
            paths.append(path)
    return paths


def read_lid_state_details() -> tuple[str | None, tuple[tuple[str, str | None, str], ...]]:
    """Return the aggregated lid state plus per-path parsed details."""

    saw_open = False
    details: list[tuple[str, str | None, str]] = []
    resolved_state: str | None = None

    for path in _lid_state_paths():
        try:
            with open(path) as f:
                raw_content = f.read()
        except OSError:
            continue

        parsed_state = _parse_lid_state(raw_content)
        raw_excerpt = str(raw_content).strip().replace("\n", " ")[:80]
        details.append((path, parsed_state, raw_excerpt))

        if parsed_state == "closed":
            resolved_state = "closed"
            break
        if parsed_state == "open":
            saw_open = True

    if resolved_state is None and saw_open:
        resolved_state = "open"

    return resolved_state, tuple(details)


def read_lid_state() -> str | None:
    """Return the current lid state from available ACPI lid state files."""
    state, _details = read_lid_state_details()
    return state


def _log_lid_transition_details_if_needed(*, logger, source: str, previous: str | None, current: str, details) -> None:
    if not _brightness_debug_enabled():
        return

    logger.info(
        "EVENT power:lid_state_transition source=%s previous=%s current=%s details=%s",
        str(source),
        previous,
        current,
        details,
    )


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
        lid_files = [path for path in _lid_state_paths() if _path_exists(path)]

        if not lid_files:
            logger.warning("No lid state file found")
            return

        logger.info("Monitoring lid state from: %s", ", ".join(lid_files))

        last_state = None
        while is_running():

            def poll_once() -> None:
                nonlocal last_state
                state, details = read_lid_state_details()

                if state and state != last_state:
                    logger.info("Lid state changed: %s -> %s", last_state, state)
                    _log_lid_transition_details_if_needed(
                        logger=logger,
                        source="sysfs_monitor",
                        previous=last_state,
                        current=state,
                        details=details,
                    )
                    if state == "closed":
                        on_lid_close()
                    elif state == "open":
                        on_lid_open()
                    last_state = state

            if not _run_lid_monitor_action(action=poll_once, logger=logger):
                break

            time.sleep(0.5)

    threading.Thread(target=monitor_lid_sysfs, daemon=True).start()


def _path_exists(path: str) -> bool:
    try:
        with open(path):
            return True
    except OSError:
        return False
    except _LID_MONITOR_RUNTIME_ERRORS:
        return True


def poll_lid_state_paths(
    *,
    is_running: Callable[[], bool],
    on_lid_close: Callable[[], None],
    on_lid_open: Callable[[], None],
    logger,
) -> None:
    """Fallback: poll lid state from known /proc or /sys paths."""

    if not any(_path_exists(path) for path in _lid_state_paths()):
        logger.warning("Could not find lid state file, power management disabled")
        return

    last_state = None
    while is_running():

        def poll_once() -> None:
            nonlocal last_state
            parsed, details = read_lid_state_details()

            if parsed and parsed != last_state:
                _log_lid_transition_details_if_needed(
                    logger=logger,
                    source="fallback_poll",
                    previous=last_state,
                    current=parsed,
                    details=details,
                )
                if parsed == "closed":
                    on_lid_close()
                elif parsed == "open":
                    on_lid_open()
                last_state = parsed

        _run_lid_monitor_action(action=poll_once, logger=logger)

        time.sleep(1)
