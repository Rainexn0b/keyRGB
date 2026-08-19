from __future__ import annotations

from typing import Final

# Baseline multiplier for software loops.
# Historically this was intentionally slow; software effects now aim to feel closer
# to hardware effects (snappier) while still allowing the speed slider to slow
# things down when desired.
DEFAULT_SOFTWARE_SLOWDOWN: Final[float] = 0.8


def get_interval(base_ms: int, *, speed: int, slowdown: float = DEFAULT_SOFTWARE_SLOWDOWN) -> float:
    """Calculate interval based on speed (0-10, 10 = fastest).

    Historically the software effects were effectively capped near the base
    interval even at low speeds. Use the full 1..11x multiplier so speed 0
    is meaningfully slower.
    """

    speed_factor = max(1, min(11, 11 - int(speed)))

    # Global slowdown for software effects.
    # Tuned by feel: low UI speeds (e.g. 2) should be noticeably slow.
    return (base_ms * float(speed_factor) * float(slowdown)) / 1000.0


def clamped_interval(
    base_ms: int,
    *,
    speed: int,
    min_s: float,
    slowdown: float = DEFAULT_SOFTWARE_SLOWDOWN,
) -> float:
    interval = get_interval(base_ms, speed=speed, slowdown=slowdown)
    return max(float(min_s), float(interval))


def brightness_factor(brightness: int) -> float:
    """Convert the hardware brightness scale (0-50) to a 0..1 factor."""

    return float(brightness) / 50.0
