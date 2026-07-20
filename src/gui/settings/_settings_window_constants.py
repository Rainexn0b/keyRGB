"""Constants and small helpers for the settings window.

Extracted from ``window.py`` (WS1 / B2 slice 1).
"""

from __future__ import annotations

import importlib

from src.core.power.system import PowerMode


def detect_idle_power_source() -> str:
    """Best-effort probe for the idle source the tray would use.

    Uses a dynamic import so the settings GUI does not take a static
    dependency on tray runtime modules.
    """
    try:
        module = importlib.import_module("src.tray.pollers.idle_power._source_probe")
        fn = getattr(module, "detect_idle_power_source")
        return str(fn())
    except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError):
        return "Unknown"


KEEP_CURRENT_POWER_MODE_LABEL = "Keep current power mode"
POWER_MODE_OPTIONS = (
    KEEP_CURRENT_POWER_MODE_LABEL,
    "Extreme Saver",
    "Balanced",
    "Performance",
)
POWER_MODE_LABEL_TO_VALUE = {
    "Extreme Saver": PowerMode.EXTREME_SAVER.value,
    "Balanced": PowerMode.BALANCED.value,
    "Performance": PowerMode.PERFORMANCE.value,
}
POWER_MODE_VALUE_TO_LABEL = {value: label for label, value in POWER_MODE_LABEL_TO_VALUE.items()}

SETTINGS_MIN_WIDTH = 1000
SETTINGS_MIN_HEIGHT = 620
SETTINGS_DEFAULT_WIDTH = 1320
SETTINGS_DEFAULT_HEIGHT = 860
SETTINGS_COLUMN_GAP = 22
