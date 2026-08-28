from __future__ import annotations

import colorsys

# UI brightness range shared across backends (0..50). Backend-neutral.
UI_BRIGHTNESS_MAX = 50


def clamp_channel(value: int) -> int:
    return max(0, min(255, int(value)))


def hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    """Convert HSV to RGB (h: 0-1, s: 0-1, v: 0-1)."""

    r, g, b = colorsys.hsv_to_rgb(float(h), float(s), float(v))
    return (int(r * 255), int(g * 255), int(b * 255))


def scale_color_for_brightness(color, brightness: int) -> tuple[int, int, int]:
    """Scale an RGB color by a UI brightness level (0..50), backend-neutral.

    Channels are int-converted and clamped to 0..255. At brightness <= 0 the
    result is black; at the maximum UI brightness the channels are clamped
    directly; in between each channel is rounded after multiplying by
    brightness/50 and then clamped.
    """

    red, green, blue = color
    level = max(0, min(UI_BRIGHTNESS_MAX, int(brightness)))
    if level <= 0:
        return (0, 0, 0)
    if level >= UI_BRIGHTNESS_MAX:
        return (clamp_channel(red), clamp_channel(green), clamp_channel(blue))

    scale = level / UI_BRIGHTNESS_MAX
    return (
        clamp_channel(round(int(red) * scale)),
        clamp_channel(round(int(green) * scale)),
        clamp_channel(round(int(blue) * scale)),
    )
