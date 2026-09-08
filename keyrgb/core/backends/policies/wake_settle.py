"""Backend-declared controller wake-settle policy."""

from __future__ import annotations

import math

DEFAULT_CONTROLLER_WAKE_SETTLE_S = 2.5


def normalize_controller_wake_settle_s(value: object) -> float:
    if isinstance(value, bool):
        return DEFAULT_CONTROLLER_WAKE_SETTLE_S
    if isinstance(value, int):
        parsed = float(value)
    elif isinstance(value, float):
        parsed = value
    else:
        return DEFAULT_CONTROLLER_WAKE_SETTLE_S
    if not math.isfinite(parsed):
        return DEFAULT_CONTROLLER_WAKE_SETTLE_S
    if parsed == 0.0:
        return 0.0
    if parsed < 0.0:
        return DEFAULT_CONTROLLER_WAKE_SETTLE_S
    return parsed


def controller_wake_settle_s(kb: object) -> float:
    return normalize_controller_wake_settle_s(getattr(kb, "keyrgb_controller_wake_settle_s", None))
