from __future__ import annotations

# Reactive brightness timing constants.
#
# These values control visual smoothness during restores and transitions.
# They were tuned on ITE8291R3 hardware; different hardware may need
# different values.

# --- Brightness step guard ---

# Maximum brightness change per render frame before clamping.
# Prevents single-frame jumps (e.g. 3 -> 50) from concurrent writers.
# Units: hardware brightness steps (0..50 scale).
MAX_BRIGHTNESS_STEP_PER_FRAME: int = 8

# --- Post-restore pulse visual damp ---

# Seconds after a restore during which the streak gate is bypassed and
# pulse visual scale is damped.  Prevents the first few frames after
# wake from spiking to full brightness.
POST_RESTORE_PULSE_VISUAL_HOLDOFF_S: float = 2.0

# Minimum pulse scale factor during the visual damp window.
# 0.35 means the brightest pulse in the first ~2 s after wake is scaled
# to 35 % of its configured intensity.
# Units: fraction of full pulse intensity (0.0..1.0).
POST_RESTORE_PULSE_VISUAL_MIN_FACTOR: float = 0.35

# --- Pulse mix rise/decay ---

# Per-frame decay when all pulses have ended.
# Controls how quickly the keyboard fades back to idle brightness.
PULSE_MIX_DECAY_STEP: float = 0.34

# Per-frame rise during an active burst.
PULSE_MIX_RISE_STEP: float = 0.45

# First-keypress rise after idle — deliberately smaller to avoid a
# single-frame jump to full pulse-lift strength on overlapping presses.
PULSE_MIX_INITIAL_RISE_STEP: float = 0.18

# --- Uniform backend HW-lift streak gate ---

# Number of consecutive frames with an active pulse before a uniform-only
# backend is allowed to raise hardware brightness.  Prevents the first
# keypress of a burst from producing an immediate full-frame spike.
# Units: render frames.
UNIFORM_PULSE_HW_LIFT_STREAK_MIN: int = 6

# --- First-activity hold-off ---

# Seconds after the first keypress activity during which the hardware-lift
# cooldown gate is held open.  Ensures the very first pulse can raise
# brightness without waiting for the streak count to accumulate.
FIRST_ACTIVITY_PULSE_LIFT_HOLDOFF_S: float = 0.30

# Seconds after restore during which the visual damp factor scales pulse
# brightness down to prevent a bright flash on low-brightness wake-up
# ramps.  Kept in sync with POST_RESTORE_PULSE_VISUAL_HOLDOFF_S.
FIRST_ACTIVITY_POST_RESTORE_VISUAL_DAMP_S: float = 2.0
