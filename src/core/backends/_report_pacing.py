from __future__ import annotations

import os
import time

DEFAULT_HID_REPORT_DELAY_S = 0.001
GLOBAL_HID_REPORT_DELAY_ENV = "KEYRGB_HID_REPORT_DELAY_MS"


def backend_report_delay_env_key(backend_name: str) -> str | None:
    """Return the per-backend delay env var for a backend name."""

    parts: list[str] = []
    current: list[str] = []
    for char in str(backend_name or "").strip():
        if char.isalnum():
            current.append(char.upper())
            continue
        if current:
            parts.append("".join(current))
            current = []
    if current:
        parts.append("".join(current))
    if not parts:
        return None
    return f"KEYRGB_{'_'.join(parts)}_REPORT_DELAY_MS"


def _delay_s_from_env_key(env_key: str) -> float | None:
    raw = os.environ.get(env_key, "")
    if not raw.strip():
        return None
    try:
        return max(0.0, float(raw) / 1000.0)
    except (TypeError, ValueError):
        return None


def hid_report_delay_s_from_env(*, backend_name: str | None = None) -> float:
    """Return the configured HID report pacing delay in seconds.

    The global ``KEYRGB_HID_REPORT_DELAY_MS`` applies to all HID/USB backends
    and defaults to 1 ms.  A backend-specific variable of the form
    ``KEYRGB_<BACKEND_NAME>_REPORT_DELAY_MS`` can override the global value for
    that backend, with punctuation normalized to underscores.  Set the variable
    to ``0`` to disable pacing.
    """

    if backend_name:
        specific_key = backend_report_delay_env_key(backend_name)
        if specific_key is not None:
            delay_s = _delay_s_from_env_key(specific_key)
            if delay_s is not None:
                return delay_s

    delay_s = _delay_s_from_env_key(GLOBAL_HID_REPORT_DELAY_ENV)
    if delay_s is not None:
        return delay_s

    return DEFAULT_HID_REPORT_DELAY_S


def sleep_after_hid_report(*, backend_name: str | None = None, delay_s: float | None = None) -> None:
    """Sleep for the configured HID report pacing delay."""

    delay = hid_report_delay_s_from_env(backend_name=backend_name) if delay_s is None else max(0.0, float(delay_s))
    if delay > 0.0:
        time.sleep(delay)
