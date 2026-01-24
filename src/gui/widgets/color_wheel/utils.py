import math
from typing import Any, Callable, Tuple

# Type aliases
# RGB color is (0..255, 0..255, 0..255)
ColorRGB = Tuple[int, int, int]


def hex_to_rgb(hex_color: str) -> ColorRGB:
    """Convert hex string (e.g. #aabbcc) to RGB tuple."""
    s = str(hex_color or "").strip()
    if not s:
        return (0x2B, 0x2B, 0x2B)
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 3:
        s = "".join([c * 2 for c in s])
    if len(s) != 6:
        return (0x2B, 0x2B, 0x2B)
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return (0x2B, 0x2B, 0x2B)


def rgb_to_hex(rgb: ColorRGB) -> str:
    """Convert RGB tuple to hex string."""
    r, g, b = (int(rgb[0]) & 0xFF, int(rgb[1]) & 0xFF, int(rgb[2]) & 0xFF)
    return f"#{r:02x}{g:02x}{b:02x}"


def derive_border_hex(bg_rgb: ColorRGB) -> str:
    """Derive a subtle border color from background for both themes."""
    r, g, b = (float(bg_rgb[0]), float(bg_rgb[1]), float(bg_rgb[2]))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b

    if lum >= 160.0:
        # Light background: darken for border
        rr, gg, bb = (int(r * 0.75), int(g * 0.75), int(b * 0.75))
    else:
        # Dark background: lighten for border
        rr = int(r + (255.0 - r) * 0.35)
        gg = int(g + (255.0 - g) * 0.35)
        bb = int(b + (255.0 - b) * 0.35)

    return rgb_to_hex((rr, gg, bb))


def invoke_callback(cb: Callable[..., Any] | None, *args: Any, **kwargs: Any) -> None:
    """Invoke a callback, preserving backwards compatibility.

    Older callbacks in this codebase expect exactly three positional args
    (r, g, b). Newer code may accept optional keyword metadata.
    """
    if cb is None:
        return
    try:
        cb(*args, **kwargs)
    except TypeError:
        # Fallback for old-style callbacks that don't accept kwargs
        cb(*args)


def hsv_to_xy(hue: float, saturation: float, radius: float) -> Tuple[float, float]:
    """Calculate X, Y coordinates on the wheel from Hue and Saturation.

    hue: 0..1
    saturation: 0..1
    radius: wheel radius in pixels
    """
    angle = hue * 2 * math.pi
    distance = saturation * (radius - 20)  # -20 for center circle area

    x = radius + distance * math.cos(angle)
    y = radius + distance * math.sin(angle)
    return x, y


def xy_to_hsv(x: int, y: int, radius: float) -> Tuple[float, float] | None:
    """Calculate Hue and Saturation from X, Y coordinates.

    Returns (hue, saturation) tuple, or None if outside the wheel.
    hue: 0..1
    saturation: 0..1
    """
    dx = x - radius
    dy = y - radius
    distance = math.sqrt(dx * dx + dy * dy)

    # Clamp to wheel radius (minus center circle)
    max_distance = radius - 20
    if distance > radius:
        return None  # Outside wheel

    if distance < 20:
        # In center circle area
        return None, 0.0  # Special case: saturation 0, hue unchanged (handled by caller)

    angle = math.atan2(dy, dx)
    if angle < 0:
        angle += 2 * math.pi

    hue = angle / (2 * math.pi)
    saturation = min(distance / max_distance, 1.0)
    return hue, saturation
