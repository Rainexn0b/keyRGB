from __future__ import annotations

import colorsys
import logging
import time
from dataclasses import dataclass
from typing import Any

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.reactive.input import (
    EvdevKeyboardDevices,
    close_evdev_keyboards,
    poll_keypress_slot_ids,
    try_open_evdev_keyboards,
)

# Type alias
Color = tuple[int, int, int]


def _srgb_channel_to_linear(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb: Color) -> float:
    r, g, b = rgb
    rl = _srgb_channel_to_linear(r / 255.0)
    gl = _srgb_channel_to_linear(g / 255.0)
    bl = _srgb_channel_to_linear(b / 255.0)
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def _contrast_ratio(a: Color, b: Color) -> float:
    la = _relative_luminance(a)
    lb = _relative_luminance(b)
    lighter = max(la, lb)
    darker = min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _pick_contrasting_highlight(*, base_rgb: Color, preferred_rgb: Color) -> Color:
    """Pick a highlight that stays visible over the base.

    We prefer the user's chosen color when it has enough contrast; otherwise fall
    back to a high-contrast alternative.
    """
    # If the preferred highlight already stands out, keep it.
    if _contrast_ratio(base_rgb, preferred_rgb) >= 2.2:
        return preferred_rgb

    inv = (255 - preferred_rgb[0], 255 - preferred_rgb[1], 255 - preferred_rgb[2])
    candidates: list[Color] = [preferred_rgb, inv, (255, 255, 255), (0, 0, 0)]

    best = preferred_rgb
    best_ratio = 0.0
    for c in candidates:
        ratio = _contrast_ratio(base_rgb, c)
        if ratio > best_ratio:
            best_ratio = ratio
            best = c
    return best


def _rgb_to_hsv01(rgb: Color) -> tuple[float, float, float]:
    r, g, b = rgb
    return colorsys.rgb_to_hsv(float(r) / 255.0, float(g) / 255.0, float(b) / 255.0)


def _brightness_boost_pulse(*, base_rgb: Color) -> Color:
    """Generate a visible pulse by brightening/whitening the base color.

    This produces a "flash" effect that's visible on ANY base color by:
    1. Significantly boosting brightness
    2. Reducing saturation to add white

    This is more universally visible than hue shifting, which can produce
    similar-looking colors for some base colors (e.g., cyan -> blue).
    """
    h, s, v = _rgb_to_hsv01(base_rgb)

    # Reduce saturation to add white/pastel effect (makes pulse lighter)
    # Boost value to maximum for bright flash
    s = max(0.0, float(s) * 0.3)  # Reduce saturation significantly
    v = 1.0  # Maximum brightness

    return hsv_to_rgb(h, s, v)


@dataclass
class _Pulse:
    row: int
    col: int
    age_s: float
    ttl_s: float


@dataclass
class _RainbowPulse:
    row: int
    col: int
    age_s: float
    ttl_s: float
    hue_offset: float


@dataclass
class _PressSource:
    devices: EvdevKeyboardDevices
    synthetic: bool
    spawn_interval_s: float
    allow_synthetic: bool = False
    spawn_acc: float = 0.0
    reopen_interval_s: float = 2.0
    reopen_acc_s: float = 0.0

    def poll_slot_ids(self, *, dt: float) -> list[str]:
        """Return all slot ids pressed since the last poll.

        For synthetic mode (no evdev devices), returns [""] when a synthetic
        press should be spawned, and [] otherwise. The empty string preserves
        the historical "unmapped press" sentinel used by the effect loops.
        """
        slot_ids = poll_keypress_slot_ids(self.devices)
        if slot_ids:
            return slot_ids

        if not self.devices:
            self.reopen_acc_s += float(dt)
            if self.reopen_acc_s >= float(self.reopen_interval_s):
                self.reopen_acc_s = 0.0
                reopened = try_open_evdev_keyboards() or []
                if reopened:
                    self.devices = reopened
                    self.synthetic = False

        if self.synthetic and self.allow_synthetic:
            self.spawn_acc += float(dt)
            if self.spawn_acc >= float(self.spawn_interval_s):
                self.spawn_acc = 0.0
                return [""]

        return []

    def poll_slot_id(self, *, dt: float) -> str | None:
        """Return a slot id (string) when pressed.

        For synthetic mode (no evdev devices), returns an empty string "" when
        a synthetic press should be spawned, and None otherwise.
        """
        slot_ids = self.poll_slot_ids(dt=dt)
        return slot_ids[0] if slot_ids else None

    def close(self) -> None:
        close_evdev_keyboards(self.devices)
        self.devices = []


def _ripple_weight(*, d: int, radius: float, intensity: float, band: float) -> float:
    """Compute an expanding-ring ripple weight.

    `d` is a Manhattan distance from the pulse center.
    """
    if band <= 0.0:
        return 0.0
    return max(0.0, float(intensity) * (1.0 - (abs(float(d) - float(radius)) / float(band))))


def _ripple_radius(*, age_s: float, ttl_s: float, min_radius: float = 0.0, max_radius: float = 8.0) -> float:
    if ttl_s <= 0.0:
        return float(min_radius)
    t = max(0.0, min(1.0, float(age_s) / float(ttl_s)))
    return float(min_radius + (max_radius - min_radius) * t)


def _age_pulses_in_place(pulses: list[Any], *, dt: float) -> list[Any]:
    write_idx = 0
    for pulse in pulses:
        pulse.age_s += dt
        if pulse.age_s <= pulse.ttl_s:
            pulses[write_idx] = pulse
            write_idx += 1
    del pulses[write_idx:]
    return pulses


# Maximum real frame delta applied to pulse aging. Caps the visible "jump"
# after scheduling stalls (suspend, GC pause, busy USB bus) so a slow frame
# fast-forwards gracefully instead of teleporting the animation.
MAX_FRAME_DT_S: float = 0.25


def frame_elapsed_dt_s(*, now_s: float, last_frame_s: float | None, nominal_dt_s: float) -> float:
    """Real seconds elapsed since the previous frame, clamped to a sane range.

    Aging pulses by the measured frame delta (instead of the nominal 1/60)
    keeps animation speed constant in wall-clock time even when render work
    makes frames late. The first frame uses the nominal dt.
    """
    if last_frame_s is None:
        return float(nominal_dt_s)
    elapsed = float(now_s) - float(last_frame_s)
    if elapsed <= 0.0:
        return 0.0
    return min(elapsed, MAX_FRAME_DT_S)


def remaining_frame_delay_s(*, frame_start_s: float, nominal_dt_s: float) -> float:
    """Sleep budget left in the current frame after render work.

    Compensates for evdev polling / overlay building / USB writes so the loop
    period stays near nominal_dt_s instead of nominal_dt_s + work time, which
    is the main source of effective-frame-rate jitter in the reactive loops.
    """
    remaining = float(nominal_dt_s) - (time.monotonic() - float(frame_start_s))
    return max(0.0, remaining)


# Per-effect EWMA of frame work time. On slow backends (ITE8291R3 needs ~45ms
# of USB writes per frame) the nominal 60fps budget is unreachable, so a fixed
# threshold would flag every frame. The overrun diagnostic instead measures
# against the backend's own recent norm: a hitch is a frame that is slow
# *relative to its neighbours*.
_FRAME_WORK_EWMA: dict[str, float] = {}
_FRAME_WORK_EWMA_ALPHA: float = 0.05  # ~20-frame horizon


def log_frame_overrun_if_slow(
    *,
    logger: Any,
    frame_start_s: float,
    nominal_dt_s: float,
    effect_name: str,
    threshold_factor: float = 1.5,
) -> None:
    """DEBUG-log when a frame's work exceeded the adaptive frame budget.

    A late frame is the visible "hitch mid-propagation" artifact: the render
    thread was stalled (typically by concurrent USB I/O under kb_lock, e.g.
    the 2s hardware poller's synchronous get_brightness/is_off reads). One
    extra monotonic call per frame; logging itself is throttled.
    """
    from src.core.utils.logging_utils import log_throttled

    work_s = time.monotonic() - float(frame_start_s)
    key = str(effect_name)
    avg = _FRAME_WORK_EWMA.get(key, float(nominal_dt_s))
    avg = avg + _FRAME_WORK_EWMA_ALPHA * (work_s - avg)
    _FRAME_WORK_EWMA[key] = avg
    budget_s = max(float(nominal_dt_s), avg) * float(threshold_factor)
    if work_s <= budget_s:
        return
    log_throttled(
        logger,
        f"effects.reactive.frame_overrun.{effect_name}",
        interval_s=10.0,
        level=logging.DEBUG,
        msg=(
            f"Reactive {effect_name} frame overran budget: work={work_s * 1000.0:.1f}ms "
            f"budget={budget_s * 1000.0:.1f}ms (likely concurrent kb_lock USB I/O)"
        ),
    )


def pulse_decay_ease_out(*, age_s: float, ttl_s: float) -> float:
    """Ease-out decay: 1.0 at birth, 0.0 at ttl, zero slope at the end.

    A linear (1 - t) tail visibly snaps off on 8-bit LED hardware; the power
    curve decelerates into black so the tail dissolves smoothly. Exponent 1.5
    (rather than a full quadratic) keeps mid-life brightness perceptible on
    dim decks while preserving the gentle tail-off.
    """
    if ttl_s <= 0.0:
        return 0.0
    t = max(0.0, min(1.0, float(age_s) / float(ttl_s)))
    remaining = 1.0 - t
    return remaining**1.5
