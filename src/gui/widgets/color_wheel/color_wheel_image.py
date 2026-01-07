"""Color wheel image generation and caching helpers.

This module is intentionally UI-free (no tkinter) so it can be tested and
maintained independently of widget code.
"""

from __future__ import annotations

import colorsys
import math
import os
from pathlib import Path


def wheel_cache_path(*, size: int) -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    cache_root = Path(xdg) if xdg else (Path.home() / ".cache")
    return cache_root / "keyrgb" / f"color_wheel_{int(size)}.ppm"


def build_wheel_ppm_bytes(*, size: int, bg_rgb: tuple[int, int, int], center_size: int) -> bytes:
    """Build a PPM (P6) wheel image as bytes."""

    radius = int(size) // 2
    max_distance = max(1.0, float(radius - int(center_size)))
    two_pi = 2.0 * math.pi

    bg_r, bg_g, bg_b = (
        int(bg_rgb[0]) & 0xFF,
        int(bg_rgb[1]) & 0xFF,
        int(bg_rgb[2]) & 0xFF,
    )

    data = bytearray(int(size) * int(size) * 3)
    idx = 0
    for y in range(int(size)):
        dy = (y + 0.5) - radius
        for x in range(int(size)):
            dx = (x + 0.5) - radius
            dist = math.hypot(dx, dy)

            if dist > radius:
                r8, g8, b8 = bg_r, bg_g, bg_b
            elif dist < int(center_size):
                r8, g8, b8 = 255, 255, 255
            else:
                angle = math.atan2(dy, dx)
                if angle < 0:
                    angle += two_pi
                hue = angle / two_pi
                sat = min(dist / max_distance, 1.0)
                r, g, b = colorsys.hsv_to_rgb(hue, sat, 1.0)
                r8, g8, b8 = int(r * 255), int(g * 255), int(b * 255)

            data[idx] = r8
            data[idx + 1] = g8
            data[idx + 2] = b8
            idx += 3

    header = f"P6\n{int(size)} {int(size)}\n255\n".encode("ascii")
    return header + bytes(data)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Atomic write (tmp + replace)."""

    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
        except Exception:
            pass
