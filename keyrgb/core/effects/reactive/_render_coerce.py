from __future__ import annotations

import os

_INT_COERCION_ERRORS = (TypeError, ValueError, OverflowError)


def coerce_int(value: object, *, default: int | None) -> int | None:
    try:
        return int(value)  # type: ignore[call-overload]
    except _INT_COERCION_ERRORS:
        return default


def coerce_float(value: object, *, default: float | None) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except _INT_COERCION_ERRORS:
        return default


def coerce_brightness(value: object, *, default: int | None) -> int | None:
    coerced = coerce_int(value, default=default)
    if coerced is None:
        return None
    return max(0, min(50, coerced))


def debug_brightness_enabled() -> bool:
    return os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1"
