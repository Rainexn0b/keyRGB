from __future__ import annotations

# Tuned to feel deliberate without making idle and wake transitions laggy.
# Keep soft-on slightly slower so low-brightness restore ramps read less stepped.
SOFT_OFF_FADE_DURATION_S = 0.20
SOFT_ON_FADE_DURATION_S = 0.42
SOFT_ON_START_BRIGHTNESS = 1
