from __future__ import annotations

from src.core.utils.safe_attrs import safe_float_attr

# Tuned to feel deliberate without making idle and wake transitions laggy.
# Keep soft-on slightly slower so low-brightness restore ramps read less stepped.
SOFT_ON_START_BRIGHTNESS = 1

# User-adjustable lighting fade (Settings -> Screen idle/blanking sync).
# The previous fixed durations (0.20s off / 0.42s on) completed in 3-6 hardware
# frames on USB-paced ITE controllers and read as an instant step rather than a
# fade, so the default is deliberately slower and configurable.
DEFAULT_IDLE_FADE_DURATION_S = 0.6
MIN_IDLE_FADE_DURATION_S = 0.1
MAX_IDLE_FADE_DURATION_S = 3.0


def idle_fade_duration_s(config: object) -> float:
    """Return the configured idle/power lighting fade duration in seconds."""

    return safe_float_attr(
        config,
        "idle_fade_duration_s",
        default=DEFAULT_IDLE_FADE_DURATION_S,
        min_v=MIN_IDLE_FADE_DURATION_S,
        max_v=MAX_IDLE_FADE_DURATION_S,
    )
