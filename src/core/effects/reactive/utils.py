from __future__ import annotations

import colorsys
from dataclasses import dataclass
from typing import Any, List, Tuple

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.reactive.input import poll_keypress_key_id

# Type alias
Color = Tuple[int, int, int]


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
    candidates: List[Color] = [preferred_rgb, inv, (255, 255, 255), (0, 0, 0)]

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
    devices: list
    synthetic: bool
    spawn_interval_s: float
    spawn_acc: float = 0.0

    def poll_key_id(self, *, dt: float) -> str | None:
        """Return a key id (string) when pressed.

        For synthetic mode (no evdev devices), returns an empty string "" when
        a synthetic press should be spawned, and None otherwise.
        """
        key_id = poll_keypress_key_id(self.devices)
        if key_id:
            return str(key_id)

        if self.synthetic:
            self.spawn_acc += float(dt)
            if self.spawn_acc >= float(self.spawn_interval_s):
                self.spawn_acc = 0.0
                return ""

        return None


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


def _age_pulses_in_place(pulses: List[Any], *, dt: float) -> List[Any]:
    new_pulses: List[Any] = []
    for pulse in pulses:
        pulse.age_s += dt
        if pulse.age_s <= pulse.ttl_s:
            new_pulses.append(pulse)
    return new_pulses
