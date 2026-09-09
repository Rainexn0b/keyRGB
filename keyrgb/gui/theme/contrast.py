"""Pure WCAG contrast helpers for the shared Tk theme.

These helpers are intentionally Tk-free so unit tests can pin the
normal-text (4.5:1), large title-text (3:1), and disabled-text usability
(3:1) targets without constructing widgets.
"""

from __future__ import annotations

import re

_HEX_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{6})$")


def parse_hex_color(value: str) -> tuple[int, int, int]:
    """Parse a strict ``#rrggbb`` color into an ``(r, g, b)`` tuple.

    Only six-digit hexadecimal colors are accepted. Short ``#rgb`` forms,
    alpha suffixes, surrounding whitespace, and named colors raise
    :class:`ValueError`.
    """

    if not isinstance(value, str):
        raise TypeError(f"hex color must be str, got {type(value).__name__}")
    match = _HEX_COLOR_RE.match(value)
    if match is None:
        raise ValueError(f"invalid hex color: {value!r} (expected '#rrggbb')")
    digits = match.group(1)
    return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


def _linearize_channel(channel: int) -> float:
    value = channel / 255.0
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(color: str) -> float:
    """Return the WCAG relative luminance of a ``#rrggbb`` color."""

    red, green, blue = parse_hex_color(color)
    return 0.2126 * _linearize_channel(red) + 0.7152 * _linearize_channel(green) + 0.0722 * _linearize_channel(blue)


def contrast_ratio(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio between two ``#rrggbb`` colors."""

    lum_fg = relative_luminance(foreground)
    lum_bg = relative_luminance(background)
    lighter = max(lum_fg, lum_bg)
    darker = min(lum_fg, lum_bg)
    return (lighter + 0.05) / (darker + 0.05)


def meets_contrast(foreground: str, background: str, threshold: float) -> bool:
    """Return True when ``foreground``/``background`` meets ``threshold``."""

    return contrast_ratio(foreground, background) >= threshold


__all__ = [
    "contrast_ratio",
    "meets_contrast",
    "parse_hex_color",
    "relative_luminance",
]
