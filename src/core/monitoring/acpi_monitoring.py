from __future__ import annotations

import subprocess
from collections.abc import Callable

from .lid_monitoring import poll_lid_state_paths


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

            if "button/lid" in line.lower():
                if "close" in line.lower():
                    on_lid_close()
                elif "open" in line.lower():
                    on_lid_open()

    except FileNotFoundError:
        poll_lid_state_paths(
            is_running=is_running,
            on_lid_close=on_lid_close,
            on_lid_open=on_lid_open,
            logger=logger,
        )
